import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from datalight import models as m
from datalight import rules, service
from datalight.api import create_app


def prepared(started, monitor=True):
    settings, factory, rid = started
    service.replay(factory, settings, *service.claim(factory, "replay"))
    settings.llm_enabled = True
    settings.llm_endpoint = "http://localhost/model"
    client = TestClient(create_app(settings, factory))
    if monitor:
        client.post(f"/api/v1/runs/{rid}/control", json={"action": "resume"})
        service.replay(factory, settings, *service.claim(factory, "replay"))
    return settings, factory, rid, client


def answer(request):
    summary = json.loads(json.loads(request.content)["messages"][1]["content"])
    content = {
        "text": "The current evidence supports this decision.",
        "evidence_ids": [summary["decision"]["evidence_id"]],
    }
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}}]})


@pytest.mark.parametrize("leased", [False, True])
def test_new_analysis_finishes_pending_question_and_history_can_continue(started, leased):
    settings, factory, rid, client = prepared(started)
    decision = client.get(f"/api/v1/runs/{rid}/decisions").json()[0]
    path = f"/api/v1/findings/{decision['id']}"
    first = client.post(path + "/reviews", json={"action": "question", "reason": "Why?"})
    completed = service.claim(factory, "question")
    service.interpret(factory, settings, *completed, transport=httpx.MockTransport(answer))
    prior_answer = client.get(path + "/answers").json()[0]
    second = client.post(path + "/reviews", json={"action": "question", "reason": "Explain further."})
    assert first.status_code == second.status_code == 201

    def start_new(request=None):
        assert client.post("/api/v1/runs", json={"interval": 0}).status_code == 201
        return answer(request) if request else None

    if leased:
        pending = service.claim(factory, "question")
        service.interpret(factory, settings, *pending, transport=httpx.MockTransport(start_new))
        # Even a duplicate delivery of the old lease cannot append another answer.
        service.interpret(factory, settings, *pending, transport=httpx.MockTransport(answer))
    else:
        start_new()
    answers = client.get(path + "/answers").json()
    assert len(answers) == 2 and answers[0] == prior_answer
    assert answers[1]["review_id"] == second.json()["id"]
    assert answers[1]["status"] == "unavailable"
    assert answers[1]["text"] == "A new analysis was started."
    with factory() as session:
        assert session.get(m.Job, completed[0]).status == "done"
        job = session.scalar(select(m.Job).where(m.Job.task_key == second.json()["id"]))
        assert job.status == "cancelled" and job.lease_token is None and job.lease_until is None

    assert client.post(
        path + "/reviews", json={"action": "question", "reason": "Can you explain that now?"}
    ).status_code == 201
    service.interpret(
        factory, settings, *service.claim(factory, "question"), transport=httpx.MockTransport(answer)
    )
    assert [a["status"] for a in client.get(path + "/answers").json()] == [
        "succeeded", "unavailable", "succeeded",
    ]
    assert client.get(f"/api/v1/runs/{rid}/decisions").json()[0]["decision"] == decision["decision"]


@pytest.mark.parametrize("leased", [False, True])
def test_new_analysis_finishes_pending_rule_proposal(started, leased):
    settings, factory, rid, client = prepared(started, monitor=False)
    path = f"/api/v1/runs/{rid}/rule-proposals"
    response = client.post(path, json={"request": "Flag a fault if signal_a exceeds 70."})
    assert response.status_code == 201
    pid = response.json()["id"]

    def start_new(request=None):
        assert client.post("/api/v1/runs", json={"interval": 0}).status_code == 201
        content = {"rule": {"id": "proposal", "channel_id": "c001", "operator": "gt", "threshold": 70}}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}}]})

    if leased:
        job = service.claim(factory, "rule_proposal")
        rules.propose(factory, settings, *job, transport=httpx.MockTransport(start_new))
        rules.propose(factory, settings, *job, transport=httpx.MockTransport(start_new))
    else:
        start_new()
    proposal = client.get(path + f"/{pid}").json()
    assert proposal["status"] == "unavailable" and proposal["rule"] is None
    assert proposal["message"] == "A new analysis was started."


def test_cancellation_preserves_already_stored_answer(started):
    settings, factory, rid, client = prepared(started)
    finding = client.get(f"/api/v1/runs/{rid}/decisions").json()[0]
    path = f"/api/v1/findings/{finding['id']}"
    review = client.post(path + "/reviews", json={"action": "question", "reason": "Why?"}).json()
    with factory.begin() as session:
        session.add(m.Answer(review_id=review["id"], status="unavailable", text="Original result.", evidence_ids=[]))
    assert client.post("/api/v1/runs", json={"interval": 0}).status_code == 201
    answers = client.get(path + "/answers").json()
    assert len(answers) == 1 and answers[0]["text"] == "Original result."


def test_anonymous_human_assessment_labels_preserve_named_reviews(started):
    _, _, rid, client = prepared(started)
    finding = client.get(f"/api/v1/runs/{rid}/decisions").json()[0]
    path = f"/api/v1/findings/{finding['id']}/reviews"
    for action, operator, expected in [
        ("accept", None, "Accepted"),
        ("override", None, "Overridden"),
        ("accept", "QA", "Accept by QA"),
        ("override", "QA", "Override by QA"),
    ]:
        body = {"action": action, "reason": "Reviewed evidence.", "replacement": "OK"}
        if operator:
            body["operator"] = operator
        assert client.post(path, json=body).status_code == 201
        assert client.get(f"/api/v1/runs/{rid}/decisions").json()[0]["human_assessment"] == expected
