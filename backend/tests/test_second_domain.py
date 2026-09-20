"""Second-domain acceptance through the real upload, replay and model boundaries."""

import csv
import importlib.util
import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from datalight import providers, rules, service
from datalight.api import create_app

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/demo_web_service.csv"
HEADERS = ["requests_per_second", "cpu_percent", "p95_latency_ms", "error_rate_percent"]


def upload(store, tmp_path, content=None):
    settings, factory = store
    settings.upload_dir = tmp_path / "uploads"
    client = TestClient(create_app(settings, factory))
    response = client.post(
        "/api/v1/sources/upload",
        files={"file": (FIXTURE.name, content or FIXTURE.read_bytes(), "text/csv")},
    )
    assert response.status_code == 201, response.text
    source = response.json()
    preview = client.get("/api/v1/sources/preview", params={"source_id": source["id"]})
    assert len(preview.json()["channels"]) == 4
    response = client.post(
        "/api/v1/runs",
        json={"source_id": source["id"], "initial_rows": 500, "batch_rows": 100, "interval": 0},
    )
    assert response.status_code == 201, response.text
    rid = response.json()["id"]
    service.replay(factory, settings, *service.claim(factory, "replay"))
    run = client.get(f"/api/v1/runs/{rid}").json()
    assert run["status"] == "paused" and run["config"]["reader_mode"] == "rows"
    report = client.get(f"/api/v1/runs/{rid}/report").json()
    assert len(report["profiles"]) == len(report["predictions"]) == 4
    return client, rid


def replay(client, rid, store):
    settings, factory = store
    assert client.post(f"/api/v1/runs/{rid}/control", json={"action": "resume"}).status_code == 200
    while job := service.claim(factory, "replay"):
        service.replay(factory, settings, *job)
    run = client.get(f"/api/v1/runs/{rid}").json()
    assert (run["status"], run["rows_processed"]) == ("completed", 1500)
    decisions = client.get(f"/api/v1/runs/{rid}/decisions").json()
    assert len(decisions) == 10
    return sorted(decisions, key=lambda d: d["decision"]["row_start"])


def test_web_demo_reproducible(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "web_demo", ROOT / "scripts/generate_web_service_demo.py"
    )
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    regenerated = tmp_path / "demo.csv"
    generator.write_demo(regenerated)
    assert regenerated.read_bytes() == FIXTURE.read_bytes()
    with regenerated.open() as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == HEADERS and len(rows) == 1501
    assert all(len(row) == 4 and all(float(value) > 0 for value in row) for row in rows[1:])


def test_web_demo_no_rules_and_header_independence(store, tmp_path):
    normalized = []
    for content in (
        FIXTURE.read_bytes(),
        ("alpha,beta,gamma,delta\n" + FIXTURE.read_text().split("\n", 1)[1]).encode(),
    ):
        client, rid = upload(store, tmp_path, content)
        report = client.get(f"/api/v1/runs/{rid}/report").json()
        decisions = replay(client, rid, store)
        assert client.get(f"/api/v1/runs/{rid}/report").json() == report
        assert client.get(f"/api/v1/runs/{rid}").json()["config"]["rules"] == []
        assert [(d["decision"]["row_start"], d["decision"]["row_end"]) for d in decisions] == [
            (start, start + 99) for start in range(501, 1501, 100)
        ]
        assert all(d["decision"]["status"] == "OK" for d in decisions[:2])
        assert all(not d["decision"]["quality_warnings"] for d in decisions)
        triggers = [t for d in decisions for t in d["decision"]["triggers"]]
        assert triggers and all(t["channel_id"] != "c001" for t in triggers)
        for cid, start in (("c002", 701), ("c003", 801), ("c004", 901)):
            selected = [t for t in triggers if t["channel_id"] == cid]
            assert any(t["kind"] == "drift" for t in selected)
            assert all(t["detected_at"] >= start for t in selected)
        # Compare every trigger metric/interval and batch status; run-specific IDs differ.
        normalized.append(
            [
                (
                    d["decision"]["status"],
                    [
                        {k: v for k, v in t.items() if k != "evidence_ids"}
                        for t in d["decision"]["triggers"]
                    ],
                )
                for d in decisions
            ]
        )
    assert normalized[0] == normalized[1]


def assert_private(request):
    wire = json.loads(request.content)
    serialized = json.dumps(wire)
    assert all(name not in serialized for name in HEADERS)
    assert "demo_web_service" not in serialized
    payload = json.loads(wire["messages"][1]["content"])
    # Typed contracts reject extra fields; observations and scenario metadata have no slot.
    if "available_channel_ids" in payload:
        rules.RuleProposalPayload.model_validate(payload)
    else:
        providers.SummaryPayload.model_validate(payload)
        assert all(p["channel_id"] in {"c001", "c002", "c003", "c004"} for p in payload["profiles"])
    assert all(key not in serialized for key in ('"rows"', '"observations"', '"scenario"'))
    assert FIXTURE.read_text().splitlines()[1] not in serialized
    return payload


def test_web_demo_reviewed_rule_evidence_and_private_discussion(store, tmp_path):
    settings, factory = store
    settings.llm_enabled = True
    settings.llm_endpoint = "http://localhost/model"
    client, rid = upload(store, tmp_path)
    seen = []

    def explain(request):
        payload = assert_private(request)
        seen.append("initial")
        response = {
            "explanations": [
                {
                    "channel_id": p["channel_id"],
                    "text": "Synthetic test explanation; provisional reference.",
                    "evidence_ids": [p["evidence_id"], p["prediction_evidence_id"]],
                }
                for p in payload["profiles"]
                if p["channel_id"] in payload["target_channels"]
            ]
        }
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(response)}}]}
        )

    while job := service.claim(factory, "interpretation"):
        service.interpret(factory, settings, *job, transport=httpx.MockTransport(explain))
    assert client.get(f"/api/v1/runs/{rid}/report").json()["interpretation_status"] == "available"
    response = client.post(
        f"/api/v1/runs/{rid}/rule-proposals",
        json={"request": "Flag a fault if p95_latency_ms exceeds 400"},
    )
    assert response.status_code == 201
    pid = response.json()["id"]

    def propose(request):
        payload = assert_private(request)
        seen.append("proposal")
        assert payload["request"] == "Flag a fault if c003 exceeds 400"
        response = {
            "rule": {
                "id": "proposal",
                "version": 1,
                "channel_id": "c003",
                "operator": "gt",
                "threshold": 400,
                "effect": "fault",
            },
            "message": "",
        }
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(response)}}]}
        )

    rules.propose(
        factory,
        settings,
        *service.claim(factory, "rule_proposal"),
        transport=httpx.MockTransport(propose),
    )
    endpoint = f"/api/v1/runs/{rid}/rule-proposals/{pid}"
    assert client.get(endpoint).json()["status"] == "succeeded"
    assert client.get(f"/api/v1/runs/{rid}").json()["config"]["rules"] == []
    assert client.post(endpoint + "/apply").status_code == 200
    decisions = replay(client, rid, store)
    actual = set()
    for item in decisions:
        for match in item["decision"]["rule_matches"]:
            assert match["channel_id"] == "c003" and match["rule_id"] == pid
            matched_rows = {
                row
                for interval in match["intervals"]
                for row in range(interval["row_start"], interval["row_end"] + 1)
            }
            assert len(matched_rows) == match["violation_count"]
            actual.update(matched_rows)
            evidence = client.get(f"/api/v1/evidence/{match['evidence_ids'][0]}").json()
            assert evidence["details"]["rule"]["threshold"] == 400
            assert evidence["details"]["match"]["violation_count"] == len(matched_rows)
    with FIXTURE.open() as handle:
        expected = {
            i
            for i, row in enumerate(csv.DictReader(handle), 1)
            if i > 500 and float(row["p95_latency_ms"]) > 400
        }
    assert actual == expected and actual
    finding = decisions[-1]
    assert (
        client.post(
            f"/api/v1/findings/{finding['id']}/reviews",
            json={
                "action": "question",
                "reason": "Which measurements support the flagged decision, including p95_latency_ms, and do they establish a cause?",
            },
        ).status_code
        == 201
    )

    def answer(request):
        payload = assert_private(request)
        seen.append("question")
        assert "c003" in payload["question"]
        evidence = payload["decision"]["rule_evidence"][0]
        assert evidence["rule"]["threshold"] == 400 and evidence["violation_count"] == 100
        response = {
            "text": "Synthetic test answer: c003 exceeded the applied threshold in 100 observations. This does not establish a cause.",
            "evidence_ids": [payload["decision"]["evidence_id"], evidence["evidence_id"]],
        }
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(response)}}]}
        )

    service.interpret(
        factory,
        settings,
        *service.claim(factory, "question"),
        transport=httpx.MockTransport(answer),
    )
    answer = client.get(f"/api/v1/findings/{finding['id']}/answers").json()[0]
    assert answer["status"] == "succeeded" and len(answer["evidence_ids"]) == 2
    for eid in answer["evidence_ids"]:
        assert client.get(f"/api/v1/evidence/{eid}").status_code == 200
    assert seen == ["initial", "proposal", "question"]
