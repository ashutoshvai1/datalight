from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from datalight import models as m
from datalight import service
from datalight.api import create_app
from datalight.db import now
from datalight.ingestion import SourceError


def step(settings, factory):
    job = service.claim(factory, "replay")
    if job:
        service.replay(factory, settings, *job)
    return job


def test_explicit_setup_paused_report_reviews_and_restart(store):
    settings, factory = store
    service.bootstrap(factory, settings)
    client = TestClient(create_app(settings, factory))
    assert client.get("/api/v1/system").json()["run"] is None
    assert len(client.get("/api/v1/sources").json()) == 1
    preview = client.get("/api/v1/sources/preview", params={"path": settings.data_path.name}).json()
    assert len(preview["channels"]) == 4
    assert (
        client.get("/api/v1/sources/preview", params={"path": "../../escape.csv"}).status_code
        == 422
    )
    run = client.post("/api/v1/runs", json={"initial_rows": 500, "interval": 0}).json()
    rid = run["id"]
    step(settings, factory)
    assert client.get(f"/api/v1/runs/{rid}").json()["status"] == "paused"
    assert not step(settings, factory)
    report = client.get(f"/api/v1/runs/{rid}/report").json()
    assert len(report["predictions"]) == 4
    assert report["interpretation_status"] == "unavailable"
    client.post(f"/api/v1/runs/{rid}/control", json={"action": "resume"})
    step(settings, factory)
    decision = client.get(f"/api/v1/runs/{rid}/decisions").json()[0]
    path = f"/api/v1/findings/{decision['id']}/reviews"
    assert (
        client.post(path, json={"operator": "QA", "action": "override", "reason": ""}).status_code
        == 422
    )
    for replacement in ("Fault Suspected", "OK"):
        assert (
            client.post(
                path,
                json={
                    "operator": "QA",
                    "action": "override",
                    "reason": "Operator interpretation",
                    "replacement": replacement,
                },
            ).status_code
            == 201
        )
        latest = client.get(f"/api/v1/runs/{rid}/decisions").json()[0]
        assert latest["effective_status"] == replacement
        assert latest["decision"] == decision["decision"]
    assert (
        client.post(
            path, json={"operator": "QA", "action": "question", "reason": "Why this decision?"}
        ).status_code
        == 201
    )
    assert (
        client.get(f"/api/v1/findings/{decision['id']}/answers").json()[0]["status"]
        == "unavailable"
    )
    assert client.post(path, json={"operator": "QA", "action": "accept"}).status_code == 201
    latest = client.get(f"/api/v1/runs/{rid}/decisions").json()[0]
    assert latest["effective_status"] == decision["decision"]["status"]
    client.post(f"/api/v1/runs/{rid}/control", json={"action": "pause"})
    assert not step(settings, factory)
    restarted = TestClient(create_app(settings, factory))
    assert len(restarted.get(path).json()) == 4
    restarted.post(f"/api/v1/runs/{rid}/control", json={"action": "resume"})
    while step(settings, factory):
        pass
    assert client.get(f"/api/v1/runs/{rid}").json()["rows_processed"] == 1600
    decisions = client.get(f"/api/v1/runs/{rid}/decisions").json()
    assert {d["decision"]["status"] for d in decisions} == {"OK", "Fault Suspected"}
    assert len(decisions) == 11
    trace = client.get(f"/api/v1/runs/{rid}/trace?channel_id=c001").json()
    assert len(trace["points"]) == 1000 and trace["points"][-1]["row"] == 1600
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(m.Batch)) == len(decisions) + 1


def test_expired_lease_retries_without_duplicate_commits(started):
    settings, factory, _ = started
    old = service.claim(factory, "replay")
    with factory.begin() as session:
        session.get(m.Job, old[0]).lease_until = now() - timedelta(seconds=1)
    recovered = service.claim(factory, "replay")
    assert recovered[1] != old[1]
    for job in (old, recovered, recovered):
        service.replay(factory, settings, *job)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(m.Batch)) == 1
        assert session.scalar(select(m.Run)).rows_processed == 500


def test_atomic_rollback_includes_detector_state(started, monkeypatch):
    settings, factory, rid = started
    job = service.claim(factory, "replay")
    original = service.event

    def interrupt(session, run_id, kind, payload):
        if kind == "batch.committed":
            raise RuntimeError("crash before commit")
        return original(session, run_id, kind, payload)

    monkeypatch.setattr(service, "event", interrupt)
    with pytest.raises(RuntimeError):
        service.replay(factory, settings, *job)
    with factory() as session:
        run = session.get(m.Run, rid)
        assert run.cursor == 0 and run.detector_state is None
        assert session.scalar(select(func.count()).select_from(m.Evidence)) == 0
    monkeypatch.setattr(service, "event", original)
    service.replay(factory, settings, *job)
    with factory() as session:
        assert session.get(m.Run, rid).detector_state["history"]["count"] == 69


def test_changed_source_and_path_limits(started, tmp_path):
    settings, factory, rid = started
    step(settings, factory)
    client = TestClient(create_app(settings, factory))
    settings.data_path.write_text(settings.data_path.read_text() + "\n")
    client.post(f"/api/v1/runs/{rid}/control", json={"action": "resume"})
    with pytest.raises(SourceError, match="changed"):
        step(settings, factory)
    assert "changed" in client.get("/api/v1/system").json()["source_error"]
    assert client.get(f"/api/v1/runs/{rid}/trace?channel_id=c001").status_code == 409
    for body in (
        {"path": "/etc/passwd"},
        {"limits": {"unknown": {"minimum": 0}}},
        {"limits": {"signal_a": {"minimum": 10, "maximum": 1}}},
    ):
        assert client.post("/api/v1/runs", json=body).status_code == 422
    response = client.post("/api/v1/runs", json={"initial_rows": 64})
    assert response.status_code == 201
    assert len(client.get("/api/v1/runs").json()) == 2


def test_empty_invalid_and_short_files(store, tmp_path):
    settings, factory = store
    client = TestClient(create_app(settings, factory))
    for name, contents in (("empty.csv", "x\n"), ("text.csv", "x\nhello\n")):
        (tmp_path / name).write_text(contents)
        response = client.post("/api/v1/runs", json={"path": name})
        if response.status_code == 201:
            with pytest.raises(SourceError):
                step(settings, factory)
        else:
            assert response.status_code == 422
    (tmp_path / "short.csv").write_text("x\n" + "1\n" * 40)
    response = client.post("/api/v1/runs", json={"path": "short.csv"})
    step(settings, factory)
    assert client.get(f"/api/v1/runs/{response.json()['id']}").json()["status"] == "completed"
