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


def test_bootstrap_restart_pause_reviews_and_eof(store):
    settings, factory = store
    service.bootstrap(factory, settings)
    service.bootstrap(factory, settings)
    step(settings, factory)
    with TestClient(create_app(settings, factory)) as client:
        state = client.get("/api/v1/system").json()
        run_id = state["run"]["id"]
        assert len(client.get("/api/v1/runs").json()) == 1
        report = client.get(f"/api/v1/runs/{run_id}/report").json()
        assert len(report["profiles"]) == 4
        assert report["interpretation_status"] == "unavailable"
        finding = client.get(f"/api/v1/runs/{run_id}/findings").json()[0]
        review_path = f"/api/v1/findings/{finding['id']}/reviews"
        assert (
            client.post(
                review_path, json={"action": "override", "operator": "QA", "reason": ""}
            ).status_code
            == 422
        )
        for action in ("accept", "question", "override"):
            payload = {
                "action": action,
                "operator": "QA operator",
                "reason": "Synthetic review",
                "replacement": "Still provisional" if action == "override" else None,
            }
            assert client.post(review_path, json=payload).status_code == 201
        assert len(client.get(review_path).json()) == 3
        assert client.get(f"/api/v1/runs/{run_id}/findings").json()[0] == finding
        client.post(f"/api/v1/runs/{run_id}/control", json={"action": "pause"})
        assert step(settings, factory) is None
        client.post(f"/api/v1/runs/{run_id}/control", json={"action": "resume"})
        # A new worker/factory sees the committed cursor rather than re-ingesting the window.
        service.bootstrap(factory, settings)
        while step(settings, factory):
            pass
        assert client.get(f"/api/v1/runs/{run_id}").json()["rows_processed"] == 1600
        assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == "completed"
        kinds = {f["category"] for f in client.get(f"/api/v1/runs/{run_id}/findings").json()}
        assert {"quality", "deviation", "assumption"} <= kinds
        assert (
            client.post(f"/api/v1/runs/{run_id}/control", json={"action": "resume"}).status_code
            == 409
        )
    with TestClient(create_app(settings, factory)) as restarted:
        assert len(restarted.get(review_path).json()) == 3


def test_expired_lease_retries_without_duplicate_commits(store):
    settings, factory = store
    service.bootstrap(factory, settings)
    old = service.claim(factory, "replay")
    assert old
    with factory.begin() as session:
        session.get(m.Job, old[0]).lease_until = now() - timedelta(seconds=1)
    recovered = service.claim(factory, "replay")
    assert recovered and recovered[1] != old[1]
    service.replay(factory, settings, *old)
    service.replay(factory, settings, *recovered)
    service.replay(factory, settings, *recovered)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(m.Batch)) == 1
        assert session.scalar(select(m.Run)).rows_processed == 500


def test_transaction_rolls_back_cursor_and_evidence_on_failure(store, monkeypatch):
    settings, factory = store
    service.bootstrap(factory, settings)
    job = service.claim(factory, "replay")
    original = service.event

    def interrupt(session, run_id, kind, payload):
        if kind == "batch.committed":
            raise RuntimeError("simulated crash before commit")
        return original(session, run_id, kind, payload)

    monkeypatch.setattr(service, "event", interrupt)
    with pytest.raises(RuntimeError):
        service.replay(factory, settings, *job)
    with factory() as session:
        assert session.scalar(select(m.Run)).cursor == 0
        assert session.scalar(select(func.count()).select_from(m.Evidence)) == 0
    monkeypatch.setattr(service, "event", original)
    service.replay(factory, settings, *job)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(m.Batch)) == 1


def test_changed_source_rejected_and_new_run_preserves_history(store):
    settings, factory = store
    service.bootstrap(factory, settings)
    step(settings, factory)
    settings.data_path.write_text(settings.data_path.read_text() + "\n")
    job = service.claim(factory, "replay")
    with pytest.raises(SourceError, match="changed"):
        service.replay(factory, settings, *job)
    with TestClient(create_app(settings, factory)) as client:
        assert "changed" in client.get("/api/v1/system").json()["source_error"]
        response = client.post("/api/v1/runs", json={"initial_rows": 64})
        assert response.status_code == 201
        history = client.get("/api/v1/runs").json()
        assert len(history) == 2 and history[1]["status"] == "stopped"
