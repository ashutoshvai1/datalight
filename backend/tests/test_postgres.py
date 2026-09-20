"""Runs migrations and lock/recovery checks in a unique disposable PostgreSQL schema."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url

from datalight import models as m
from datalight import service
from datalight.config import Settings
from datalight.db import connect

pytestmark = pytest.mark.postgres


@pytest.fixture
def pg_store(dataset, monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL for real PostgreSQL verification.")
    schema = f"datalight_test_{uuid4().hex}"
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = (
        make_url(url)
        .update_query_dict({"options": f"-csearch_path={schema}"})
        .render_as_string(hide_password=False)
    )
    monkeypatch.setenv("DATABASE_URL", isolated)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[1] / "migrations")
    )
    command.upgrade(config, "head")
    command.check(config)
    settings = Settings(
        database_url=isolated,
        data_path=dataset,
        data_dir=dataset.parent,
        batch_interval=0,
        llm_enabled=False,
        _env_file=None,
    )
    engine, factory = connect(isolated)
    try:
        yield settings, factory
    finally:
        engine.dispose()
        # Only the unique schema created by this fixture is removed.
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_postgres_claims_setup_and_replay_are_unique(pg_store):
    from fastapi.testclient import TestClient

    from datalight.api import create_app

    settings, factory = pg_store
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: service.bootstrap(factory, settings), range(2)))
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(m.Run)) == 0
    client = TestClient(create_app(settings, factory))
    rid = client.post("/api/v1/runs", json={"interval": 0}).json()["id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: service.claim(factory, "replay"), range(2)))
    assert sum(c is not None for c in claims) == 1
    service.replay(factory, settings, *next(c for c in claims if c))
    assert client.get(f"/api/v1/runs/{rid}").json()["status"] == "paused"
    client.post(f"/api/v1/runs/{rid}/control", json={"action": "resume"})
    while job := service.claim(factory, "replay"):
        service.replay(factory, settings, *job)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(m.Run)) == 1
        assert session.scalar(select(m.Run)).rows_processed == 1600
        assert session.scalar(select(func.count()).select_from(m.Batch)) == 12
        assert (
            session.scalar(
                select(func.count()).select_from(m.Finding).where(m.Finding.category == "decision")
            )
            == 11
        )


def test_postgres_evidence_rejects_mutation(pg_store):
    from sqlalchemy.exc import DBAPIError

    settings, factory = pg_store
    from datalight.schemas import RunConfig

    with factory.begin() as session:
        service.create_run(
            session, service.register_source(session, settings), RunConfig(interval=0)
        )
    service.replay(factory, settings, *service.claim(factory, "replay"))
    with pytest.raises(DBAPIError, match="append-only"):
        with factory.begin() as session:
            session.execute(text("UPDATE evidence SET kind = 'changed'"))


def test_postgres_only_one_question_can_be_pending(pg_store):
    from fastapi.testclient import TestClient
    from pydantic import SecretStr

    from datalight.api import create_app

    settings, factory = pg_store
    settings.llm_enabled = True
    settings.llm_api_key = SecretStr("synthetic-provider-key")
    client = TestClient(create_app(settings, factory))
    rid = client.post("/api/v1/runs", json={"interval": 0}).json()["id"]
    service.replay(factory, settings, *service.claim(factory, "replay"))
    client.post(f"/api/v1/runs/{rid}/control", json={"action": "resume"})
    service.replay(factory, settings, *service.claim(factory, "replay"))
    finding_id = client.get(f"/api/v1/runs/{rid}/decisions").json()[0]["id"]

    def ask(_):
        with TestClient(create_app(settings, factory)) as requester:
            return requester.post(
                f"/api/v1/findings/{finding_id}/reviews",
                json={"action": "question", "reason": "Explain the evidence."},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(ask, range(2))) == [201, 409]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(m.Review)) == 1
        assert session.scalar(
            select(func.count()).select_from(m.Job).where(m.Job.kind == "question")
        ) == 1



@pytest.mark.parametrize("operation", ["config", "apply"])
def test_postgres_first_play_serializes_monitoring_changes(pg_store, operation):
    from threading import Barrier

    from fastapi.testclient import TestClient

    from datalight.api import create_app
    from datalight.schemas import MonitoringRule, RuleProposalView

    settings, factory = pg_store
    app = create_app(settings, factory)
    client = TestClient(app)
    created = client.post("/api/v1/runs", json={"interval": 0})
    assert created.status_code == 201
    rid = created.json()["id"]
    service.replay(factory, settings, *service.claim(factory, "replay"))
    proposal_id = str(uuid4())
    proposal = RuleProposalView(
        id=proposal_id,
        status="succeeded",
        rule=MonitoringRule(id=proposal_id, channel_id="c001", operator="gt", threshold=1),
    )
    with factory.begin() as session:
        session.add(
            m.Job(
                run_id=rid,
                kind="rule_proposal",
                task_key=proposal_id,
                status="done",
                payload={"result": proposal.model_dump()},
            )
        )
    barrier = Barrier(2)
    change_path = (
        f"/api/v1/runs/{rid}/monitoring-config"
        if operation == "config"
        else f"/api/v1/runs/{rid}/rule-proposals/{proposal_id}/apply"
    )
    change_body = {"excluded_channel_ids": ["c002"], "rule_ids": []}

    def request(play):
        with TestClient(app) as participant:
            barrier.wait(timeout=10)
            if play:
                return participant.post(f"/api/v1/runs/{rid}/control", json={"action": "resume"})
            return participant.post(
                change_path, json=change_body if operation == "config" else None
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        played, changed = list(pool.map(request, (True, False)))
    assert played.status_code == 200, played.text
    assert changed.status_code in (200, 409), changed.text
    config = client.get(f"/api/v1/runs/{rid}").json()["config"]
    assert config["monitoring_locked"] is True
    if operation == "config":
        assert config["excluded_channel_ids"] == (["c002"] if changed.status_code == 200 else [])
    else:
        assert [rule["id"] for rule in config["rules"]] == (
            [proposal_id] if changed.status_code == 200 else []
        )
    with factory() as session:
        events = session.scalars(
            select(m.AuditEvent).where(m.AuditEvent.run_id == rid).order_by(m.AuditEvent.id)
        ).all()
        lock = next(
            event
            for event in events
            if event.kind == "run.control" and event.payload["action"] == "resume"
        )
        assert not any(
            event.id > lock.id and event.kind in ("monitoring.configured", "rule.applied")
            for event in events
        )
    assert (
        client.post(change_path, json=change_body if operation == "config" else None).status_code
        == 409
    )
    assert client.get(f"/api/v1/runs/{rid}").json()["config"] == config
