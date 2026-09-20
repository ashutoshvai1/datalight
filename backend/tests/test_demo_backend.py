import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from datalight import models as m
from datalight import rules, service
from datalight.api import create_app
from datalight.ingestion import read_window
from datalight.schemas import MonitoringRule


def step(settings, factory):
    job = service.claim(factory, "replay")
    if job:
        service.replay(factory, settings, *job)
    return job


def upload_run(store, tmp_path):
    settings, factory = store
    settings.upload_dir = tmp_path / "uploads"
    client = TestClient(create_app(settings, factory))
    csv = "sample,pressure,other,note\n" + "".join(
        f"{1 if i % 5 == 0 else 99},{i},{i % 4},ok\n" for i in range(200)
    )
    response = client.post(
        "/api/v1/sources/upload", files={"file": ("../example.csv", csv, "text/csv")}
    )
    assert response.status_code == 201, response.text
    source = response.json()
    assert source["name"] == "example.csv"
    preview = client.get("/api/v1/sources/preview", params={"source_id": source["id"]})
    assert preview.json()["channels"] == ["pressure", "other"]
    response = client.post(
        "/api/v1/runs",
        json={"source_id": source["id"], "initial_rows": 60, "batch_rows": 20, "interval": 0},
    )
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["config"]["reader_mode"] == "rows"
    step(settings, factory)
    return settings, factory, client, run["id"]


def test_upload_generic_row_order_exclusion_lock_and_history(store, tmp_path):
    settings, factory, client, rid = upload_run(store, tmp_path)
    report = client.get(f"/api/v1/runs/{rid}/report").json()
    assert all(c["status"] != "fail" for c in report["checks"] if "sample" in c["name"])
    original = report["predictions"]
    endpoint = f"/api/v1/runs/{rid}/monitoring-config"
    assert (
        client.post(
            endpoint, json={"excluded_channel_ids": ["c001", "c002"], "rule_ids": []}
        ).status_code
        == 422
    )
    assert (
        client.post(endpoint, json={"excluded_channel_ids": ["c002"], "rule_ids": []}).status_code
        == 200
    )
    assert client.post(f"/api/v1/runs/{rid}/control", json={"action": "resume"}).status_code == 200
    for _ in range(5):
        step(settings, factory)
    decisions = client.get(f"/api/v1/runs/{rid}/decisions").json()
    assert decisions[0]["decision"]["coverage"]["total"] == 1
    assert set(decisions[0]["decision"]["forecast_errors"]) == {"c001"}
    assert all(
        not d["decision"]["confidence"] or d["decision"]["confidence"]["basis"]["channel_id"] == "c001"
        for d in decisions
    )
    with factory() as session:
        assert set(session.get(m.Run, rid).detector_state["channels"]) == {"c001"}
    assert client.get(f"/api/v1/runs/{rid}/report").json()["predictions"] == original
    assert (
        client.post(endpoint, json={"excluded_channel_ids": [], "rule_ids": []}).status_code == 409
    )
    client.post(f"/api/v1/runs/{rid}/control", json={"action": "pause"})
    assert (
        client.post(endpoint, json={"excluded_channel_ids": [], "rule_ids": []}).status_code == 409
    )
    trace = client.get(
        f"/api/v1/runs/{rid}/trace", params={"channel_id": "c001", "batch_window": 3}
    ).json()
    assert (trace["start_batch"], trace["end_batch"], trace["latest_batch"]) == (3, 5, 5)
    assert (trace["row_start"], trace["row_end"], len(trace["points"])) == (101, 160, 60)
    earlier = client.get(
        f"/api/v1/runs/{rid}/trace",
        params={"channel_id": "c001", "batch_window": 3, "end_batch": 4},
    ).json()
    assert (earlier["row_start"], earlier["row_end"]) == (81, 140)
    overlap = {p["row"]: p["forecast"] for p in trace["points"]}
    assert all(
        overlap[p["row"]] == pytest.approx(p["forecast"])
        for p in earlier["points"]
        if p["row"] in overlap
    )
    assert (
        client.get(
            f"/api/v1/runs/{rid}/trace", params={"channel_id": "c002", "batch_window": 3}
        ).status_code
        == 422
    )
    restarted = TestClient(create_app(settings, factory))
    assert restarted.get(f"/api/v1/runs/{rid}").json()["config"]["monitoring_locked"]
    assert restarted.get(f"/api/v1/runs/{rid}/trace?channel_id=c001").status_code == 200


def test_upload_validation_and_cleanup(store, tmp_path):
    settings, factory = store
    settings.upload_dir = tmp_path / "uploads"
    settings.max_upload_bytes = 100
    client = TestClient(create_app(settings, factory))
    for content, status in [
        ("", 422),
        ("a,a\n1,2\n", 422),
        ("x,y\na,b\n", 422),
        ("x\n" + "1\n" * 100, 413),
        (b"x\n\xff", 422),
    ]:
        assert (
            client.post("/api/v1/sources/upload", files={"file": ("test.csv", content)}).status_code
            == status
        )
        assert not list(settings.upload_dir.iterdir())
    assert (
        client.post("/api/v1/sources/upload", files={"file": ("bad.exe", "x\n1")}).status_code
        == 422
    )


def propose(client, settings, factory, rid, effect="fault", channel="c001"):
    settings.llm_enabled = True
    settings.llm_endpoint = "http://localhost/model"
    requested = client.post(
        f"/api/v1/runs/{rid}/rule-proposals",
        json={"request": "Flag a fault if pressure exceeds 70"},
    )
    assert requested.status_code == 201, requested.text
    pid = requested.json()["id"]

    def respond(request):
        wire = json.loads(request.content)
        payload = json.loads(wire["messages"][1]["content"])
        assert "pressure" not in json.dumps(wire)
        assert payload == {
            "request": "Flag a fault if c001 exceeds 70",
            "available_channel_ids": ["c001", "c002"],
        }
        answer = {
            "rule": {
                "id": "proposal",
                "version": 1,
                "channel_id": channel,
                "operator": "gt",
                "threshold": 70,
                "effect": effect,
            },
            "message": "",
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(answer)}}]})

    job = service.claim(factory, "rule_proposal")
    rules.propose(factory, settings, *job, transport=httpx.MockTransport(respond))
    return pid


def test_proposal_review_apply_privacy_and_rule_evidence(store, tmp_path):
    settings, factory, client, rid = upload_run(store, tmp_path)
    pid = propose(client, settings, factory, rid)
    endpoint = f"/api/v1/runs/{rid}/rule-proposals/{pid}"
    proposal = client.get(endpoint).json()
    assert proposal["status"] == "succeeded" and proposal["rule"]["id"] == pid
    assert client.get(f"/api/v1/runs/{rid}").json()["config"]["rules"] == []
    applied = client.post(endpoint + "/apply").json()
    assert applied["config"]["rules"][0]["id"] == pid
    assert len(client.post(endpoint + "/apply").json()["config"]["rules"]) == 1
    assert (
        client.post(
            f"/api/v1/runs/{rid}/monitoring-config",
            json={"excluded_channel_ids": ["c001"], "rule_ids": [pid]},
        ).status_code
        == 422
    )
    client.post(f"/api/v1/runs/{rid}/control", json={"action": "resume"})
    step(settings, factory)
    decision = client.get(f"/api/v1/runs/{rid}/decisions").json()[0]["decision"]
    match = decision["rule_matches"][0]
    assert decision["status"] == "Fault Suspected"
    assert (match["violation_count"], match["row_start"], match["row_end"]) == (9, 72, 80)
    evidence = client.get(f"/api/v1/evidence/{match['evidence_ids'][0]}").json()
    assert evidence["kind"] == "rule" and evidence["details"]["rule"]["threshold"] == 70
    assert client.post(endpoint + "/apply").status_code == 409
    finding = client.get(f"/api/v1/runs/{rid}/decisions").json()[0]
    question = client.post(
        f"/api/v1/findings/{finding['id']}/reviews",
        json={"operator": "QA", "action": "question", "reason": "Why did this rule flag a fault?"},
    )
    assert question.status_code == 201

    def answer_rule(request):
        wire = json.loads(request.content)
        summary = json.loads(wire["messages"][1]["content"])
        supplied = summary["decision"]["rule_evidence"][0]
        assert supplied["rule"]["threshold"] == 70
        assert supplied["violation_count"] == 9
        assert summary["decision"]["confidence"] == decision["confidence"]
        assert summary["decision"]["confidence"]["level"] == "low"
        assert summary["decision"]["confidence"]["basis"]["observed_persistence"] == 9
        assert "row_start" not in supplied and "pressure" not in json.dumps(wire)
        answer = {
            "text": "The explicit fault rule exceeded 70 in nine observations.",
            "evidence_ids": [summary["decision"]["evidence_id"], supplied["evidence_id"]],
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(answer)}}]})

    service.interpret(
        factory,
        settings,
        *service.claim(factory, "question"),
        transport=httpx.MockTransport(answer_rule),
    )
    assert (
        client.get(f"/api/v1/findings/{finding['id']}/answers").json()[0]["status"] == "succeeded"
    )
    with factory() as session:
        assert session.scalar(select(m.ModelCall)).status == "succeeded"


def test_unavailable_invalid_proposals_and_exclusion_revalidation(store, tmp_path):
    settings, factory, client, rid = upload_run(store, tmp_path)
    path = f"/api/v1/runs/{rid}/rule-proposals"
    result = client.post(path, json={"request": "Warn if pressure exceeds 2"}).json()
    assert result["status"] == "unavailable"
    assert client.post(path + f"/{result['id']}/apply").status_code == 409
    assert client.post(path, json={"request": "faultNumber exceeds 1"}).status_code == 422
    assert client.post(path, json={"request": "pressure values 1 2 3 4 5"}).status_code == 422
    invalid = propose(client, settings, factory, rid, channel="c999")
    assert client.get(path + f"/{invalid}").json()["status"] == "failed"
    valid = propose(client, settings, factory, rid)
    client.post(
        f"/api/v1/runs/{rid}/monitoring-config",
        json={"excluded_channel_ids": ["c001"], "rule_ids": []},
    )
    assert client.post(path + f"/{valid}/apply").status_code == 422


def test_rule_boundaries_missing_and_quality_no_temporal_masking(tmp_path):
    path = tmp_path / "input.csv"
    path.write_text('value\n0\n1\n2\n""\ninvalid\n')
    window = read_window(path, 0, 100, reader_mode="rows")
    configured = [
        MonitoringRule(id="a", channel_id="c001", operator="outside", minimum=0, maximum=1),
        MonitoringRule(id="b", channel_id="c001", operator="missing"),
    ]
    matches = rules.evaluate(window, [("c001", "value")], configured, "prefix", 1)
    assert [(match.rule_id, match.violation_count, match.row_start) for match in matches] == [
        ("a", 1, 3),
        ("b", 1, 4),
    ]
    assert all(match.effect == "quality_warning" for match in matches)
    assert window.rows[2][0] == "2"


def test_quality_rule_warning_does_not_set_process_status(store, tmp_path):
    settings, factory, client, rid = upload_run(store, tmp_path)
    pid = propose(client, settings, factory, rid, effect="quality_warning")
    client.post(f"/api/v1/runs/{rid}/rule-proposals/{pid}/apply")
    client.post(f"/api/v1/runs/{rid}/control", json={"action": "resume"})
    step(settings, factory)
    decision = client.get(f"/api/v1/runs/{rid}/decisions").json()[0]["decision"]
    assert decision["status"] == "OK" and decision["rule_matches"][0]["violation_count"] == 9
    assert any(pid in warning for warning in decision["quality_warnings"])


def test_sparse_rule_matches_retain_actual_intervals(tmp_path):
    path = tmp_path / "sparse.csv"
    path.write_text("value\n2\n2\n0\n2\n")
    rule = MonitoringRule(id="a", channel_id="c001", operator="gt", threshold=1)
    match = rules.evaluate(read_window(path, 0, 100), [("c001", "value")], [rule], "prefix", 10)[0]
    assert match.violation_count == 3
    assert [(interval.row_start, interval.row_end) for interval in match.intervals] == [
        (10, 11),
        (13, 13),
    ]
