import asyncio
import json
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from . import analysis, providers, rules, service, sources, temporal
from . import models as m
from . import schemas as s
from .analysis import safe as analysis_safe
from .config import Settings
from .db import connect, now
from .ingestion import SourceError, Window, finite, read_window


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

    @app.post("/api/v1/sources/upload", response_model=s.SourceView, status_code=201)
    async def upload_source(session: DB, file: Annotated[UploadFile, File()]):
        name = Path((file.filename or "upload.csv").replace("\\", "/")).name
        if not name.lower().endswith(".csv"):
            raise HTTPException(422, "Choose a CSV file.")
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        destination = settings.upload_dir / f"{uuid4()}.csv"
        temporary = destination.with_suffix(".part")
        committed = False
        try:
            size = 0
            with temporary.open("xb") as handle:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > settings.max_upload_bytes:
                        raise HTTPException(413, "CSV exceeds the configured upload size limit.")
                    handle.write(chunk)
            window = read_window(temporary, 0, 100, reader_mode="rows")
            if not window.rows:
                raise SourceError("CSV has no observations.")
            if not analysis.classify(window)[1]:
                raise SourceError("No numeric channels found in the uploaded CSV preview.")
            temporary.replace(destination)
            source = service.register_source(session, settings, str(destination))
            source.name = name[:255]
            session.commit()
            committed = True
            return source
        except (SourceError, OSError) as exc:
            raise HTTPException(
                422,
                str(exc) if isinstance(exc, SourceError) else "CSV could not be stored locally.",
            ) from exc
        finally:
            await file.close()
            temporary.unlink(missing_ok=True)
            if not committed:
                destination.unlink(missing_ok=True)

    @app.get("/api/v1/sources/preview", response_model=s.SourcePreview)
    def source_preview(session: DB, path: str | None = None, source_id: str | None = None):
        try:
            if source_id:
                source = session.get(m.Source, source_id)
                if source is None:
                    raise HTTPException(404, "Source not found")
                path = str(service.source_path(source, settings))
            if not path:
                raise SourceError("Choose a CSV file.")
            mode = (
                "rows"
                if sources.resolve(settings, path).is_relative_to(settings.upload_dir.resolve())
                else "legacy"
            )
            return sources.preview(settings, path, mode)
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
                    human_assessment=(
                        {"accept": "Accepted", "override": "Overridden"}[review.action]
                        if review.operator == "Local user"
                        else f"{review.action.capitalize()} by {review.operator}"
                    )
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
    def trace(
        run_id: str,
        channel_id: str,
        session: DB,
        limit: int = Query(1000, ge=1, le=1000),
        end_batch: int | None = Query(None, ge=0),
        batch_window: int | None = Query(None, ge=1, le=3),
    ):
        run = get_run(session, run_id)
        if not run.report:
            return dict(channel_id=channel_id, points=[], flagged=[])
        profile = next((p for p in run.report["profiles"] if p["id"] == channel_id), None)
        if profile is None:
            raise HTTPException(404, "Channel not found")
        config = s.RunConfig.model_validate(run.config)
        if channel_id in config.excluded_channel_ids:
            raise HTTPException(422, "This channel is excluded from monitoring.")
        try:
            path = service.source_path(session.get(m.Source, run.source_id), settings)
            latest = session.scalar(
                select(m.Batch)
                .where(m.Batch.run_id == run.id)
                .order_by(m.Batch.index.desc())
                .limit(1)
            )
            if latest is None:
                return dict(channel_id=channel_id, points=[], flagged=[])
            last_index = latest.index if end_batch is None else end_batch
            last = session.scalar(
                select(m.Batch).where(m.Batch.run_id == run.id, m.Batch.index == last_index)
            )
            if last is None:
                raise HTTPException(404, "Batch not found")
            if batch_window is not None or end_batch is not None:
                selected = session.scalars(
                    select(m.Batch)
                    .where(m.Batch.run_id == run.id, m.Batch.index <= last.index)
                    .order_by(m.Batch.index.desc())
                    .limit(batch_window or 3)
                ).all()
                first = selected[-1].row_start
                start_batch = selected[-1].index
            else:
                first = max(1, last.row_end - limit + 1)
                start_batch = None
            context_start = max(1, first - temporal.HISTORY)
            batch = session.scalar(
                select(m.Batch)
                .where(m.Batch.run_id == run.id, m.Batch.row_start <= context_start)
                .order_by(m.Batch.row_start.desc())
                .limit(1)
            )
            if batch is None:
                return dict(channel_id=channel_id, points=[], flagged=[])
            # Read bounded source chunks and retain just chart channel/order context.
            cursor, remaining, sequence, previous = (
                batch.summary["start_offset"],
                last.row_end - batch.row_start + 1,
                batch.summary.get("start_sequence", batch.sequence),
                None,
            )
            compact = None
            while remaining > 0:
                chunk = read_window(
                    path,
                    cursor,
                    min(remaining, 10000),
                    previous,
                    sequence,
                    split_sequences=False,
                    reader_mode=config.reader_mode,
                )
                if not chunk.rows:
                    break
                selected_indexes = [chunk.header.index(profile["name"])]
                if chunk.sample_index is not None and chunk.sample_index not in selected_indexes:
                    selected_indexes.append(chunk.sample_index)
                if compact is None:
                    compact = Window(
                        [chunk.header[i] for i in selected_indexes],
                        [],
                        [],
                        0,
                        0,
                        None,
                        False,
                        sample_index=selected_indexes.index(chunk.sample_index)
                        if chunk.sample_index is not None
                        else None,
                    )
                compact.rows.extend([[row[i] for i in selected_indexes] for row in chunk.rows])
                compact.segments.extend(chunk.segments)
                compact.invalid_records.extend(chunk.invalid_records)
                cursor, previous, sequence = chunk.cursor, chunk.last_sample, chunk.sequence
                remaining -= len(chunk.rows)
            if compact is None:
                return dict(channel_id=channel_id, points=[], flagged=[])
            values, segments, _ = temporal.vectors(
                compact, profile["name"], config.limits.get(profile["name"])
            )
            forecasts = temporal.features(values, segments)["forecast"]
            points = [
                dict(
                    row=batch.row_start + i,
                    sequence=int(segments[i]),
                    value=finite(row[0]),
                    forecast=analysis_safe(forecasts[i]),
                )
                for i, row in enumerate(compact.rows)
                if batch.row_start + i >= first
            ]
            findings = session.scalars(
                select(m.Finding).where(
                    m.Finding.run_id == run.id,
                    m.Finding.category == "decision",
                    m.Finding.batch_index >= batch.index,
                    m.Finding.batch_index <= last.index,
                )
            ).all()
            flagged = [
                {**t, "row_start": max(first, t["row_start"]), "row_end": min(last.row_end, t["row_end"])}
                for finding in findings
                for t in finding.details["triggers"]
                if t["channel_id"] == channel_id
                and t["row_end"] >= first
                and t["row_start"] <= last.row_end
            ]
            return dict(
                channel_id=channel_id,
                points=points,
                flagged=flagged,
                start_batch=start_batch if start_batch is not None else batch.index,
                end_batch=last.index,
                latest_batch=latest.index,
                row_start=first,
                row_end=last.row_end,
            )
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
            if config.source_id:
                source = session.get(m.Source, config.source_id)
                if source is None:
                    raise HTTPException(404, "Source not found")
                source_path = service.source_path(source, settings)
            else:
                source = service.register_source(session, settings, config.path)
                source_path = sources.resolve(settings, source.path)

        except SourceError as exc:
            raise HTTPException(422, str(exc)) from exc
        mode = "rows" if source_path.is_relative_to(settings.upload_dir.resolve()) else "legacy"
        preview = sources.preview(settings, source.path, mode)
        if set(config.limits) - set(preview["channels"]):
            raise HTTPException(422, "Limits must refer to numeric channels in the selected file.")
        config = config.model_copy(
            update={
                "analysis_version": "monitor-v2",
                "threshold": 6,
                "reader_mode": mode,
                "source_id": source.id,
                "excluded_channel_ids": [],
                "rules": [],
                "monitoring_locked": False,
            }
        )
        for old in session.scalars(
            select(m.Run)
            .where(m.Run.status.in_(["initializing", "running", "paused"]))
            .with_for_update()
        ):
            old.status = "stopped"
            for job in session.scalars(
                select(m.Job)
                .where(m.Job.run_id == old.id, m.Job.status.in_(["queued", "leased"]))
                .with_for_update()
            ):
                service.cancel_pending_job(session, job, "A new analysis was started.")
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
            if not run.report:
                raise HTTPException(
                    409, "Wait for initial understanding before starting monitoring."
                )
            config = s.RunConfig.model_validate(run.config)
            run.config = config.model_copy(update={"monitoring_locked": True}).model_dump()
            run.status = "running"
        else:
            run.fast_forward = body.action == "fast_forward"
        for job in session.scalars(
            select(m.Job).where(m.Job.run_id == run.id, m.Job.kind == "replay").with_for_update()
        ):
            job.available_at = now()
        service.event(session, run.id, "run.control", {"action": body.action})
        session.commit()
        return run

    def editable_run(session, run_id):
        run = session.scalar(select(m.Run).where(m.Run.id == run_id).with_for_update())
        if not run:
            raise HTTPException(404, "Run not found")
        try:
            return run, rules.editable(run)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/v1/runs/{run_id}/monitoring-config", response_model=s.RunView)
    def monitoring_config(run_id: str, body: s.MonitoringConfig, session: DB):
        run, config = editable_run(session, run_id)
        known = {p["id"] for p in run.report["profiles"]}
        excluded = set(body.excluded_channel_ids)
        if excluded - known or not known - excluded:
            raise HTTPException(422, "Keep at least one known numeric channel for monitoring.")
        if set(body.rule_ids) - {rule.id for rule in config.rules}:
            raise HTTPException(422, "Only already applied rules can be retained.")
        kept = [rule for rule in config.rules if rule.id in body.rule_ids]
        if any(rule.channel_id in excluded for rule in kept):
            raise HTTPException(422, "Remove rules for excluded channels before saving.")
        run.config = config.model_copy(
            update={"excluded_channel_ids": sorted(excluded), "rules": kept}
        ).model_dump()
        service.event(
            session,
            run.id,
            "monitoring.configured",
            {"excluded_channel_ids": sorted(excluded), "rule_ids": body.rule_ids},
        )
        session.commit()
        return run

    @app.post(
        "/api/v1/runs/{run_id}/rule-proposals", response_model=s.RuleProposalView, status_code=201
    )
    def new_rule_proposal(run_id: str, body: s.RuleProposalCreate, session: DB):
        run, config = editable_run(session, run_id)
        report = s.ReportView.model_validate(run.report)
        if not body.request.strip():
            raise HTTPException(422, "Describe a monitoring rule.")
        try:
            # Reject non-monitorable header references locally before model egress.
            import re

            allowed = rules.eligible(run, config)
            forbidden = [column.name for column in report.columns if column.role != "numeric"] + [
                p.name for p in report.profiles if p.id not in allowed
            ]
            if any(
                re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", body.request, re.IGNORECASE)
                for name in forbidden
            ):
                raise ValueError("Rules must refer to included numeric channels.")
            request = providers.question_text(body.request, report, settings)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        proposal_id = str(uuid4())
        unavailable = settings.interpretation_unavailable
        result = s.RuleProposalView(
            id=proposal_id,
            status="unavailable" if unavailable else "pending",
            message=unavailable or "",
        )
        payload = {
            "request": rules.RuleProposalPayload(
                request=request, available_channel_ids=sorted(allowed)
            ).model_dump()
        }
        if unavailable:
            payload["result"] = result.model_dump()
        session.add(
            m.Job(
                run_id=run.id,
                kind="rule_proposal",
                task_key=proposal_id,
                payload=payload,
                status="done" if unavailable else "queued",
            )
        )
        service.event(session, run.id, "rule.requested", {"proposal_id": proposal_id})
        session.commit()
        return result

    @app.get(
        "/api/v1/runs/{run_id}/rule-proposals/{proposal_id}", response_model=s.RuleProposalView
    )
    def rule_proposal(run_id: str, proposal_id: str, session: DB):
        get_run(session, run_id)
        result = rules.view(session, run_id, proposal_id)
        if result is None:
            raise HTTPException(404, "Rule proposal not found")
        return result

    @app.post("/api/v1/runs/{run_id}/rule-proposals/{proposal_id}/apply", response_model=s.RunView)
    def apply_rule(run_id: str, proposal_id: str, session: DB):
        run, config = editable_run(session, run_id)
        proposal = rules.view(session, run_id, proposal_id)
        if proposal is None:
            raise HTTPException(404, "Rule proposal not found")
        if proposal.status != "succeeded" or not proposal.rule:
            raise HTTPException(409, "A successful rule proposal is required.")
        if proposal.rule.channel_id not in rules.eligible(run, config):
            raise HTTPException(422, "The proposed channel is no longer included.")
        if not any(rule.id == proposal.rule.id for rule in config.rules):
            run.config = config.model_copy(
                update={"rules": [*config.rules, proposal.rule]}
            ).model_dump()
            service.event(session, run.id, "rule.applied", {"rule": proposal.rule.model_dump()})
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
