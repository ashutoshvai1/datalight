import json

import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select

from datalight import models as m
from datalight import providers, service
from datalight.api import create_app
from datalight.schemas import ReportView


def prepare(started):
    settings, factory, rid = started
    settings.llm_enabled = True
    settings.llm_api_key = SecretStr("fixture-only-secret")
    service.replay(factory, settings, *service.claim(factory, "replay"))
    with factory() as session:
        report = ReportView.model_validate(session.get(m.Run, rid).report)
    return settings, factory, rid, providers.summarize(report)


def response_for(summary, bad=False):
    if summary.question is not None:
        content = {
            "text": "The decision follows the supplied thresholds; it is not a diagnosis.",
            "evidence_ids": [summary.decision.evidence_ids[0]],
        }
    else:
        content = {
            "explanations": [
                {
                    "channel_id": p.channel_id,
                    "text": "Observed variation and forecast errors describe behavior, not a physical role.",
                    "evidence_ids": [
                        "invented" if bad else p.evidence_id,
                        p.prediction_evidence_id,
                    ],
                }
                for p in summary.profiles
            ]
        }
    return {"choices": [{"message": {"content": json.dumps(content)}}]}


def transport(seen=None, bad=False):
    def handler(request):
        body = json.loads(request.content)
        summary = providers.SummaryPayload.model_validate_json(body["messages"][1]["content"])
        if seen is not None:
            seen.append(body)
        for forbidden in (
            "faultNumber",
            "simulationRun",
            "fault_status",
            "signal_a",
            "fixture-only-secret",
            '"rows"',
            '"samples"',
        ):
            assert forbidden not in json.dumps(body)
        return httpx.Response(200, json=response_for(summary, bad))

    return httpx.MockTransport(handler)


def test_all_channel_egress_and_audit(started):
    settings, factory, rid, _ = prepare(started)
    seen = []
    service.interpret(
        factory, settings, *service.claim(factory, "interpretation"), transport=transport(seen)
    )
    with factory() as session:
        call = session.scalar(select(m.ModelCall))
        assert call.status == "succeeded" and call.request == seen[0]
        report = session.get(m.Run, rid).report
        assert report["interpretation_status"] == "available"
        assert len(report["explanations"]) == len(report["profiles"]) == 4
        for explanation in report["explanations"]:
            assert all(session.get(m.Evidence, eid) for eid in explanation["evidence_ids"])


def test_grouped_jobs_cover_every_channel_and_partial_failure(started):
    settings, factory, rid = started
    settings.data_path.write_text(
        ",".join(f"channel_{i}" for i in range(19))
        + "\n"
        + "\n".join(",".join(str(row + i) for i in range(19)) for row in range(100))
    )
    # Re-register the changed fixture as an explicit new analysis.
    client = TestClient(create_app(settings, factory))
    settings.llm_enabled = True
    settings.llm_api_key = SecretStr("fixture-only-secret")
    rid = client.post("/api/v1/runs", json={"initial_rows": 80, "interval": 0}).json()["id"]
    service.replay(factory, settings, *service.claim(factory, "replay"))
    count = 0
    while job := service.claim(factory, "interpretation"):
        service.interpret(factory, settings, *job, transport=transport(bad=count == 1))
        count += 1
    with factory() as session:
        report = session.get(m.Run, rid).report
        assert count == 3 and report["interpretation_status"] == "partial"
        assert len(report["explanations"]) == 11


def test_invalid_missing_duplicate_coverage_and_timeout(started):
    settings, factory, rid, summary = prepare(started)
    payload = providers.request_payload(summary, settings.llm_model)
    for mode in ("missing", "duplicate", "evidence"):
        reply = response_for(summary, bad=mode == "evidence")
        content = json.loads(reply["choices"][0]["message"]["content"])
        if mode == "missing":
            content["explanations"].pop()
        if mode == "duplicate":
            content["explanations"][-1] = content["explanations"][0]
        reply["choices"][0]["message"]["content"] = json.dumps(content)
        assert (
            providers.invoke(
                settings,
                summary,
                payload,
                httpx.MockTransport(lambda _, r=reply: httpx.Response(200, json=r)),
            ).status
            == "invalid"
        )
    service.interpret(
        factory, settings, *service.claim(factory, "interpretation"), transport=transport(bad=True)
    )
    with factory() as session:
        run = session.get(m.Run, rid)
        assert run.status == "paused" and run.report["interpretation_status"] == "unavailable"

    def timeout(request):
        raise httpx.ReadTimeout("timeout", request=request)

    assert (
        providers.invoke(settings, summary, payload, httpx.MockTransport(timeout)).status
        == "timeout"
    )


def test_bad_json_redirects_credentials_and_fences(started):
    settings, _, _, summary = prepare(started)
    payload = providers.request_payload(summary, settings.llm_model)
    for reply in (httpx.Response(200, text="bad JSON"), httpx.Response(200, json={"choices": []})):
        assert (
            providers.invoke(
                settings, summary, payload, httpx.MockTransport(lambda _, r=reply: r)
            ).status
            == "invalid"
        )
    assert (
        providers.invoke(
            settings,
            summary,
            payload,
            httpx.MockTransport(
                lambda _: httpx.Response(307, headers={"Location": "https://other.invalid"})
            ),
        ).status
        == "failed"
    )
    outcome = providers.invoke(
        settings,
        summary,
        payload,
        httpx.MockTransport(lambda _: httpx.Response(404, json={"error": "fixture-only-secret"})),
    )
    assert outcome.response == {"error": "[REDACTED]"}
    for fenced in (True, False):
        reply = response_for(summary)
        text = reply["choices"][0]["message"]["content"]
        reply["choices"][0]["message"]["content"] = (
            f"```json\n{text}\n```" if fenced else f"Answer: {text}"
        )
        assert providers.invoke(
            settings,
            summary,
            payload,
            httpx.MockTransport(lambda _, r=reply: httpx.Response(200, json=r)),
        ).status == ("succeeded" if fenced else "invalid")


def test_questions_are_independent_persistent_and_evidence_grounded(started):
    settings, factory, rid, _ = prepare(started)
    client = TestClient(create_app(settings, factory))
    client.post(f"/api/v1/runs/{rid}/control", json={"action": "resume"})
    service.replay(factory, settings, *service.claim(factory, "replay"))
    decision = client.get(f"/api/v1/runs/{rid}/decisions").json()[0]
    path = f"/api/v1/findings/{decision['id']}/reviews"
    for question in ("Why is signal_a OK?", "What evidence supports this decision?"):
        assert (
            client.post(
                path, json={"operator": "QA", "action": "question", "reason": question}
            ).status_code
            == 201
        )
    assert (
        client.post(
            path, json={"operator": "QA", "action": "question", "reason": "Data: 1,2,3,4,5"}
        ).status_code
        == 422
    )
    seen = []
    while job := service.claim(factory, "question"):
        service.interpret(factory, settings, *job, transport=transport(seen))
        service.interpret(factory, settings, *job, transport=transport(seen))
    assert len(seen) == 2
    answers = (
        TestClient(create_app(settings, factory))
        .get(f"/api/v1/findings/{decision['id']}/answers")
        .json()
    )
    assert len(answers) == 2 and all(a["status"] == "succeeded" for a in answers)
    assert client.get(f"/api/v1/runs/{rid}/decisions").json()[0]["decision"] == decision["decision"]


def test_question_cannot_cite_an_invented_decision_label(started):
    settings, factory, rid, _ = prepare(started)
    client = TestClient(create_app(settings, factory))
    client.post(f"/api/v1/runs/{rid}/control", json={"action": "resume"})
    service.replay(factory, settings, *service.claim(factory, "replay"))
    decision = client.get(f"/api/v1/runs/{rid}/decisions").json()[0]
    client.post(
        f"/api/v1/findings/{decision['id']}/reviews",
        json={"operator": "QA", "action": "question", "reason": "Why OK?"},
    )

    def invented(request):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"text": "No rule triggered.", "evidence_ids": ["decision"]}
                            )
                        }
                    }
                ]
            },
        )

    service.interpret(
        factory,
        settings,
        *service.claim(factory, "question"),
        transport=httpx.MockTransport(invented),
    )
    answers = client.get(f"/api/v1/findings/{decision['id']}/answers").json()
    assert answers[0]["status"] == "invalid"
