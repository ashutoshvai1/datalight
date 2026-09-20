import asyncio
import json
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from . import models as m
from . import providers, service, sources, temporal
from . import schemas as s
from .analysis import safe as analysis_safe
from .config import Settings
from .db import connect, now
from .ingestion import SourceError, finite, read_window


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
        if source:
            try:
                service.source_path(source, settings)
            except SourceError as exc:
                source_error = str(exc)
        return {
            "source": source,
            "run": run,
            "source_error": source_error,
            "model_status": settings.interpretation_unavailable
            or f"Configured: {settings.llm_model}; access is verified when a request succeeds.",
        }

    @app.get("/api/v1/sources", response_model=list[s.SourceChoice])
    def source_choices():
        return sources.choices(settings)

    @app.get("/api/v1/sources/preview", response_model=s.SourcePreview)
    def source_preview(path: str):
        try:
            return sources.preview(settings, path)
        except SourceError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/v1/runs/{run_id}/decisions", response_model=list[s.DecisionView])
    def decisions(
        run_id: str, session: DB, offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100)
    ):
        get_run(session, run_id)
        found = session.scalars(
            select(m.Finding)
            .where(m.Finding.run_id == run_id, m.Finding.category == "decision")
            .order_by(m.Finding.batch_index.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        result = []
        for finding in found:
            decision = s.Decision.model_validate(finding.details)
            # Questions do not revise an assessment. Accept restores the machine assessment.
            review = session.scalar(
                select(m.Review)
                .where(
                    m.Review.finding_id == finding.id, m.Review.action.in_(["accept", "override"])
                )
                .order_by(m.Review.created_at.desc())
                .limit(1)
            )
            result.append(
                dict(
                    id=finding.id,
                    batch_index=finding.batch_index,
                    decision=decision,
                    effective_status=review.replacement
                    if review and review.action == "override"
                    else decision.status,
                    human_assessment=f"{review.action.capitalize()} by {review.operator}"
                    if review
                    else None,
                    created_at=finding.created_at,
                )
            )
        return result

    @app.get("/api/v1/findings/{finding_id}/answers", response_model=list[s.AnswerView])
    def answers(finding_id: str, session: DB):
        return session.scalars(
            select(m.Answer)
            .join(m.Review)
            .where(m.Review.finding_id == finding_id)
            .order_by(m.Answer.created_at)
        ).all()

    @app.get("/api/v1/runs/{run_id}/trace", response_model=s.TraceView)
    def trace(run_id: str, channel_id: str, session: DB, limit: int = Query(1000, ge=1, le=1000)):
        run = get_run(session, run_id)
        if not run.report:
            return dict(channel_id=channel_id, points=[], flagged=[])
        profile = next((p for p in run.report["profiles"] if p["id"] == channel_id), None)
        if profile is None:
            raise HTTPException(404, "Channel not found")
        try:
            path = service.source_path(session.get(m.Source, run.source_id), settings)
            first = max(1, run.rows_processed - limit + 1)
            context_start = max(1, first - temporal.HISTORY)
            batch = session.scalar(
                select(m.Batch)
                .where(m.Batch.run_id == run.id, m.Batch.row_start <= context_start)
                .order_by(m.Batch.row_start.desc())
                .limit(1)
            )
            if batch is None:
                return dict(channel_id=channel_id, points=[], flagged=[])
            # At most one configured batch plus chart context is read, never the full source.
            window = read_window(
                path,
                batch.summary["start_offset"],
                run.rows_processed - batch.row_start + 1,
                sequence=batch.summary.get("start_sequence", batch.sequence),
                split_sequences=False,
            )
            config = s.RunConfig.model_validate(run.config)
            values, segments, _ = temporal.vectors(
                window, profile["name"], config.limits.get(profile["name"])
            )
            forecasts = temporal.features(values, segments)["forecast"]
            index = window.header.index(profile["name"])
            points = [
                dict(
                    row=batch.row_start + i,
                    sequence=int(segments[i]),
                    value=finite(row[index]),
                    forecast=analysis_safe(forecasts[i]),
                )
                for i, row in enumerate(window.rows)
                if batch.row_start + i >= first
            ]
            findings = session.scalars(
                select(m.Finding).where(
                    m.Finding.run_id == run.id,
                    m.Finding.category == "decision",
                    m.Finding.batch_index >= batch.index,
                )
            ).all()
            flagged = [
                t
                for f in findings
                for t in f.details["triggers"]
                if t["channel_id"] == channel_id and t["row_end"] >= first
            ]
            return dict(channel_id=channel_id, points=points, flagged=flagged)
        except SourceError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/v1/runs", response_model=list[s.RunView])
    def runs(session: DB, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        return session.scalars(
            select(m.Run).order_by(m.Run.created_at.desc()).offset(offset).limit(limit)
        ).all()

    @app.post("/api/v1/runs", response_model=s.RunView, status_code=201)
    def new_run(config: s.RunConfig, session: DB):
        service.coordination_lock(session)
        try:
            source = service.register_source(session, settings, config.path)
        except SourceError as exc:
            raise HTTPException(422, str(exc)) from exc
        preview = sources.preview(settings, source.path)
        if set(config.limits) - set(preview["channels"]):
            raise HTTPException(422, "Limits must refer to numeric channels in the selected file.")
        config = config.model_copy(update={"analysis_version": "monitor-v2", "threshold": 6})
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
        finding = session.scalar(
            select(m.Finding).where(m.Finding.id == finding_id).with_for_update()
        )
        if finding is None:
            raise HTTPException(404, "Finding not found")
        if (
            finding.category == "decision"
            and body.action == "override"
            and body.replacement not in ("OK", "Fault Suspected")
        ):
            raise HTTPException(422, "Choose OK or Fault Suspected.")
        question = None
        conversation = []
        if body.action == "question" and finding.category == "decision":
            run = get_run(session, finding.run_id)
            pending = session.scalar(
                select(m.Review.id)
                .outerjoin(m.Answer, m.Answer.review_id == m.Review.id)
                .where(
                    m.Review.finding_id == finding_id,
                    m.Review.action == "question",
                    m.Answer.id.is_(None),
                )
                .limit(1)
            )
            if pending:
                raise HTTPException(409, "Wait for the current answer before asking a follow-up.")
            report = s.ReportView.model_validate(run.report)
            try:
                question = providers.question_text(body.reason, report, settings)
                previous = session.execute(
                    select(m.Review, m.Answer)
                    .join(m.Answer, m.Answer.review_id == m.Review.id)
                    .where(
                        m.Review.finding_id == finding_id,
                        m.Review.action == "question",
                        m.Answer.status == "succeeded",
                    )
                    .order_by(m.Review.created_at.desc(), m.Review.id.desc())
                    .limit(10)
                ).all()
                conversation = [
                    providers.ConversationTurn(
                        question=providers.question_text(review.reason, report, settings),
                        answer=providers.question_text(answer.text, report, settings, answer=True),
                    ).model_dump()
                    for review, answer in reversed(previous)
                ]
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
        value = m.Review(finding_id=finding_id, **body.model_dump())
        session.add(value)
        session.flush()
        if body.action == "question" and finding.category == "decision":
            if settings.interpretation_unavailable:
                session.add(
                    m.Answer(
                        review_id=value.id,
                        status="unavailable",
                        text=settings.interpretation_unavailable,
                        evidence_ids=[],
                    )
                )
            else:
                session.add(
                    m.Job(
                        run_id=finding.run_id,
                        kind="question",
                        task_key=value.id,
                        payload={
                            "review_id": value.id,
                            "question": question,
                            "conversation": conversation,
                        },
                    )
                )
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
