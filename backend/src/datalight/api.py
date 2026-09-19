import asyncio
import json
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from . import models as m
from . import schemas as s
from . import service
from .config import Settings
from .db import connect, now
from .ingestion import SourceError, identity


def create_app(settings: Settings | None = None, session_factory=None) -> FastAPI:
    settings = settings or Settings()
    if session_factory is None:
        _, session_factory = connect(settings.database_url)
    app = FastAPI(
        title="Datalight",
        version="0.1.0",
        description="Local evidence-led monitoring and human review.",
    )

    def database():
        with session_factory() as session:
            yield session

    DB = Annotated[Session, Depends(database)]

    def get_run(session, run_id):
        value = session.get(m.Run, run_id)
        if value is None:
            raise HTTPException(404, "Run not found")
        return value

    @app.get("/healthz")
    def health(session: DB):
        session.execute(text("SELECT 1"))
        return {"status": "ok"}

    @app.get("/api/v1/system", response_model=s.SystemView)
    def system(session: DB):
        run = session.scalar(select(m.Run).order_by(m.Run.created_at.desc()).limit(1))
        source = session.get(m.Source, run.source_id) if run else None
        source_error = None
        try:
            current_identity = identity(settings.data_path)
            if source and source.identity != current_identity:
                source_error = (
                    "Mounted CSV has changed. Start a new analysis to register this source."
                )
        except SourceError as exc:
            source_error = str(exc)
        return {
            "source": source,
            "run": run,
            "source_error": source_error,
            "model_status": settings.interpretation_unavailable
            or f"Configured: {settings.llm_model}; access is verified when a request succeeds.",
        }

    @app.get("/api/v1/runs", response_model=list[s.RunView])
    def runs(session: DB, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        return session.scalars(
            select(m.Run).order_by(m.Run.created_at.desc()).offset(offset).limit(limit)
        ).all()

    @app.post("/api/v1/runs", response_model=s.RunView, status_code=201)
    def new_run(config: s.RunConfig, session: DB):
        service.coordination_lock(session)
        try:
            source = service.register_source(session, settings)
        except SourceError as exc:
            raise HTTPException(422, str(exc)) from exc
        for old in session.scalars(
            select(m.Run)
            .where(m.Run.status.in_(["initializing", "running", "paused"]))
            .with_for_update()
        ):
            old.status = "stopped"
            for job in session.scalars(
                select(m.Job).where(m.Job.run_id == old.id).with_for_update()
            ):
                job.status = "cancelled"
            service.event(
                session, old.id, "run.stopped", {"reason": "A new analysis was requested."}
            )
        run = service.create_run(session, source, config)
        session.commit()
        return run

    @app.get("/api/v1/runs/{run_id}", response_model=s.RunView)
    def run(run_id: str, session: DB):
        return get_run(session, run_id)

    @app.post("/api/v1/runs/{run_id}/control", response_model=s.RunView)
    def control(run_id: str, body: s.RunControl, session: DB):
        run = session.scalar(select(m.Run).where(m.Run.id == run_id).with_for_update())
        if not run:
            raise HTTPException(404, "Run not found")
        if run.status not in ("initializing", "running", "paused"):
            raise HTTPException(409, "This run is finished. Start a new analysis to replay it.")
        if body.action == "pause":
            run.status = "paused"
        elif body.action == "resume":
            run.status = "running" if run.report else "initializing"
        else:
            run.fast_forward = body.action == "fast_forward"
        for job in session.scalars(
            select(m.Job).where(m.Job.run_id == run.id, m.Job.kind == "replay").with_for_update()
        ):
            job.available_at = now()
        service.event(session, run.id, "run.control", {"action": body.action})
        session.commit()
        return run

    @app.get("/api/v1/runs/{run_id}/report", response_model=s.ReportView)
    def report(run_id: str, session: DB):
        run = get_run(session, run_id)
        if run.report is None:
            raise HTTPException(404, "Initial analysis is not ready yet")
        return run.report

    @app.get("/api/v1/runs/{run_id}/batches", response_model=list[s.BatchView])
    def batches(
        run_id: str,
        session: DB,
        limit: int = Query(100, ge=1, le=500),
        before: int | None = Query(None, ge=0),
    ):
        get_run(session, run_id)
        query = select(m.Batch).where(m.Batch.run_id == run_id)
        if before is not None:
            query = query.where(m.Batch.index < before)
        return session.scalars(query.order_by(m.Batch.index.desc()).limit(limit)).all()

    @app.get("/api/v1/runs/{run_id}/findings", response_model=list[s.FindingView])
    def findings(
        run_id: str,
        session: DB,
        category: str | None = None,
        offset: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=500),
    ):
        get_run(session, run_id)
        query = select(m.Finding).where(m.Finding.run_id == run_id)
        if category:
            query = query.where(m.Finding.category == category)
        return session.scalars(
            query.order_by(m.Finding.created_at.desc(), m.Finding.id).offset(offset).limit(limit)
        ).all()

    @app.get("/api/v1/evidence/{evidence_id}", response_model=s.EvidenceView)
    def evidence(evidence_id: str, session: DB):
        value = session.get(m.Evidence, evidence_id)
        if value is None:
            raise HTTPException(404, "Evidence not found")
        return value

    @app.post("/api/v1/findings/{finding_id}/reviews", response_model=s.ReviewView, status_code=201)
    def review(finding_id: str, body: s.ReviewCreate, session: DB):
        finding = session.get(m.Finding, finding_id)
        if finding is None:
            raise HTTPException(404, "Finding not found")
        value = m.Review(finding_id=finding_id, **body.model_dump())
        session.add(value)
        session.flush()
        service.event(
            session,
            finding.run_id,
            "review.created",
            {"finding_id": finding_id, "review_id": value.id, "action": body.action},
        )
        session.commit()
        return value

    @app.get("/api/v1/findings/{finding_id}/reviews", response_model=list[s.ReviewView])
    def reviews(
        finding_id: str,
        session: DB,
        offset: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=500),
    ):
        return session.scalars(
            select(m.Review)
            .where(m.Review.finding_id == finding_id)
            .order_by(m.Review.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()

    @app.get("/api/v1/runs/{run_id}/model-calls", response_model=list[s.ModelCallView])
    def calls(
        run_id: str, session: DB, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)
    ):
        get_run(session, run_id)
        return session.scalars(
            select(m.ModelCall)
            .where(m.ModelCall.run_id == run_id)
            .order_by(m.ModelCall.started_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()

    @app.get("/api/v1/runs/{run_id}/audit", response_model=list[s.EventView])
    def audit(
        run_id: str,
        session: DB,
        before: int | None = Query(None, ge=1),
        limit: int = Query(100, ge=1, le=500),
    ):
        get_run(session, run_id)
        query = select(m.AuditEvent).where(m.AuditEvent.run_id == run_id)
        if before is not None:
            query = query.where(m.AuditEvent.id < before)
        return session.scalars(query.order_by(m.AuditEvent.id.desc()).limit(limit)).all()

    @app.get("/api/v1/runs/{run_id}/events")
    async def events(
        run_id: str,
        request: Request,
        after: int = Query(0, ge=0),
        last_event_id: str | None = Header(None),
    ):
        with session_factory() as session:
            get_run(session, run_id)
        if last_event_id is not None:
            try:
                after = max(after, int(last_event_id))
            except ValueError as exc:
                raise HTTPException(400, "Last-Event-ID must be an integer") from exc

        async def stream():
            cursor = after
            while not await request.is_disconnected():
                with session_factory() as session:
                    rows = session.scalars(
                        select(m.AuditEvent)
                        .where(m.AuditEvent.run_id == run_id, m.AuditEvent.id > cursor)
                        .order_by(m.AuditEvent.id)
                        .limit(100)
                    ).all()
                    data = [s.EventView.model_validate(row).model_dump(mode="json") for row in rows]
                for item in data:
                    cursor = item["id"]
                    yield f"id: {cursor}\ndata: {json.dumps(item)}\n\n"
                if not data:
                    yield ": heartbeat\n\n"
                await asyncio.sleep(0.25 if len(data) == 100 else 1)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


app = create_app()
