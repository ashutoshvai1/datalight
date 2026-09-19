"""Transactional run orchestration. Analysis is pure; external calls occur outside transactions."""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import and_, or_, select, text

from . import analysis, providers
from . import models as m
from .config import Settings
from .db import now
from .ingestion import SourceError, fingerprint, identity, read_window
from .schemas import ChannelProfile, ReportView, RunConfig


def event(session, run_id: str, kind: str, payload: dict):
    session.add(m.AuditEvent(run_id=run_id, kind=kind, payload=payload))


def coordination_lock(session):
    if session.bind.dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(724901)"))


def create_run(session, source: m.Source, config: RunConfig) -> m.Run:
    run = m.Run(source_id=source.id, config=config.model_dump())
    session.add(run)
    session.flush()
    session.add(m.Job(run_id=run.id, kind="replay"))
    event(session, run.id, "run.created", {"config": config.model_dump(), "source_id": source.id})
    return run


def register_source(session, settings: Settings) -> m.Source:
    info = identity(settings.data_path)
    digest = fingerprint(info)
    source = session.scalar(select(m.Source).where(m.Source.fingerprint == digest))
    if source is None:
        source = m.Source(identity=info, fingerprint=digest, name=settings.data_path.name)
        session.add(source)
        session.flush()
    return source


def bootstrap(factory, settings: Settings):
    with factory.begin() as session:
        coordination_lock(session)
        if session.scalar(select(m.Run.id).limit(1)) is not None:
            return
        source = register_source(session, settings)
        create_run(
            session,
            source,
            RunConfig(
                initial_rows=settings.initial_rows,
                batch_rows=settings.batch_rows,
                interval=settings.batch_interval,
                threshold=settings.deviation_threshold,
            ),
        )


def claim(factory, kind: str) -> tuple[str, str] | None:
    with factory.begin() as session:
        current = now()
        query = (
            select(m.Job)
            .join(m.Run)
            .where(
                m.Job.kind == kind,
                m.Job.available_at <= current,
                or_(
                    m.Job.status == "queued",
                    and_(m.Job.status == "leased", m.Job.lease_until < current),
                ),
            )
        )
        if kind == "replay":
            query = query.where(m.Run.status.in_(["initializing", "running"]))
        query = (
            query.order_by(m.Job.available_at).with_for_update(skip_locked=True, of=m.Job).limit(1)
        )
        job = session.scalar(query)
        if job is None:
            return None
        token = str(uuid4())
        job.status = "leased"
        job.lease_until = current + timedelta(minutes=5)
        job.lease_token = token
        job.attempts += 1
        return job.id, token


def replay(factory, settings: Settings, job_id: str, token: str):
    # A run lock serializes controls/new-run cancellation with each small batch commit.
    with factory.begin() as session:
        job = session.get(m.Job, job_id)
        if job is None:
            return
        run = session.scalar(select(m.Run).where(m.Run.id == job.run_id).with_for_update())
        session.refresh(job, with_for_update=True)
        if job.lease_token != token or job.status != "leased":
            return
        if run.status not in ("initializing", "running"):
            job.status = "queued" if run.status == "paused" else "cancelled"
            return
        source = session.get(m.Source, run.source_id)
        if identity(settings.data_path) != source.identity:
            raise SourceError(
                "Mounted CSV changed since this run began. Start a new analysis to register the new source."
            )
        initial = run.report is None
        config = RunConfig.model_validate(run.config)
        window = read_window(
            settings.data_path,
            run.cursor,
            config.initial_rows if initial else config.batch_rows,
            run.last_sample,
            run.sequence,
            split_sequences=not initial,
        )
        if not window.rows:
            if initial:
                raise SourceError("CSV has a header but contains no observations.")
            run.status = "completed"
            job.status = "done"
            event(session, run.id, "run.completed", {"rows_processed": run.rows_processed})
            return
        prefix = f"{run.id}:b{run.batch_index}"
        if initial:
            columns, channels = analysis.classify(window)
        else:
            channels = [(p["id"], p["name"]) for p in run.report["profiles"]]
        current, vectors = analysis.profiles(window, channels, prefix)
        checks, trust = analysis.quality(window, current, prefix)
        pairs = analysis.correlations(vectors, prefix) if initial else []
        for p in current:
            session.add(
                m.Evidence(
                    id=p.evidence_id,
                    run_id=run.id,
                    batch_index=run.batch_index,
                    kind="profile",
                    details=p.model_dump(),
                )
            )
        for c in checks:
            session.add(
                m.Evidence(
                    id=c.evidence_id,
                    run_id=run.id,
                    batch_index=run.batch_index,
                    kind="quality",
                    details=c.model_dump(),
                )
            )
            if c.status == "fail":
                session.add(
                    m.Finding(
                        run_id=run.id,
                        batch_index=run.batch_index,
                        category="quality",
                        title=c.name.replace("_", " ").capitalize(),
                        explanation=f"{c.affected} issue(s). {c.explanation}",
                        confidence="measured",
                        channel_ids=[
                            p.id
                            for p in current
                            if (p.missing if c.name == "completeness" else p.invalid)
                        ]
                        if c.name in ("completeness", "validity")
                        else [],
                        evidence_ids=[c.evidence_id],
                        details={
                            "check": c.name,
                            "affected": c.affected,
                            "analysis_version": config.analysis_version,
                        },
                    )
                )
        for c in pairs:
            session.add(
                m.Evidence(
                    id=c.evidence_id,
                    run_id=run.id,
                    batch_index=0,
                    kind="correlation",
                    details=c.model_dump(),
                )
            )
        deviations, unsupported = [], []
        if initial:
            reason = settings.interpretation_unavailable
            if not reason and not any(p.usable for p in current):
                reason = (
                    "No sufficiently trustworthy numeric profiles are available for interpretation."
                )
            report = ReportView(
                profiles=current,
                correlations=pairs,
                columns=columns,
                checks=checks,
                limitations=analysis.LIMITATIONS,
                trust=trust,
                interpretation_status="unavailable" if reason else "pending",
                interpretation_message=reason
                or "Derived summaries are queued for model interpretation.",
                reference_version=f"{run.id}:reference-v1",
            )
            run.report = report.model_dump()
            reference_id = f"{prefix}:reference"
            session.add(
                m.Evidence(
                    id=reference_id,
                    run_id=run.id,
                    batch_index=0,
                    kind="reference",
                    details={
                        "rows": len(window.rows),
                        "trust": trust,
                        "assumption": analysis.LIMITATIONS[0],
                        "profile_evidence_ids": [p.evidence_id for p in current],
                    },
                )
            )
            session.add(
                m.Finding(
                    run_id=run.id,
                    batch_index=0,
                    category="assumption",
                    title="Provisional reference established",
                    explanation=analysis.LIMITATIONS[0],
                    confidence="assumption",
                    channel_ids=[],
                    evidence_ids=[reference_id],
                    details={
                        "reference_version": report.reference_version,
                        "analysis_version": config.analysis_version,
                    },
                )
            )
            if not reason:
                session.add(m.Job(run_id=run.id, kind="interpretation"))
            event(
                session,
                run.id,
                "report.created",
                {"reference_version": report.reference_version, "trust": trust},
            )
        else:
            deviations, unsupported = analysis.detect(
                current,
                [ChannelProfile.model_validate(p) for p in run.report["profiles"]],
                config.threshold,
            )
            for d in deviations:
                session.add(
                    m.Finding(
                        run_id=run.id,
                        batch_index=run.batch_index,
                        category="deviation",
                        title=f"{d['channel_id']} reference deviation",
                        explanation=f"Batch median {d['batch_median']:.5g} differs from reference median {d['reference_median']:.5g} by {d['score']:.2f} robust standard deviations (threshold {config.threshold:g}). This is not a fault diagnosis.",
                        confidence="measured",
                        channel_ids=[d["channel_id"]],
                        evidence_ids=d["evidence_ids"],
                        details={
                            **d,
                            "trust": trust,
                            "analysis_version": config.analysis_version,
                            "reference_version": run.report["reference_version"],
                        },
                    )
                )
            # Select only the first deviation episode per run for optional interpretation.
            # The unique (run, kind) job bounds model cost regardless of replay speed.
            if (
                deviations
                and not settings.interpretation_unavailable
                and session.scalar(
                    select(m.Job.id).where(
                        m.Job.run_id == run.id, m.Job.kind == "finding_interpretation"
                    )
                )
                is None
            ):
                session.add(m.Job(run_id=run.id, kind="finding_interpretation"))
        row_start = run.rows_processed + 1
        run.rows_processed += len(window.rows)
        session.add(
            m.Batch(
                run_id=run.id,
                index=run.batch_index,
                kind="initial" if initial else "monitor",
                row_start=row_start,
                row_end=run.rows_processed,
                sequence=window.sequence,
                summary={
                    "trust": trust,
                    "checks": [c.model_dump() for c in checks],
                    "channels": [
                        {
                            "id": p.id,
                            "median": p.median,
                            "q05": p.q05,
                            "q95": p.q95,
                            "valid": p.valid,
                            "usable": p.usable,
                        }
                        for p in current
                    ],
                    "deviations": len(deviations),
                    "unsupported": unsupported,
                    "start_offset": run.cursor,
                    "end_offset": window.cursor,
                },
            )
        )
        event(
            session,
            run.id,
            "batch.committed",
            {
                "batch_index": run.batch_index,
                "row_start": row_start,
                "row_end": run.rows_processed,
                "trust": trust,
                "deviations": len(deviations),
                "quality_failures": sum(c.status == "fail" for c in checks),
            },
        )
        run.cursor, run.sequence, run.last_sample = (
            window.cursor,
            window.sequence,
            window.last_sample,
        )
        run.batch_index += 1
        run.status = "completed" if window.eof else "running"
        job.status = "done" if window.eof else "queued"
        job.lease_token = None
        job.lease_until = None
        job.available_at = now() + timedelta(seconds=0 if run.fast_forward else config.interval)
        if window.eof:
            event(session, run.id, "run.completed", {"rows_processed": run.rows_processed})


def interpret(factory, settings: Settings, job_id: str, token: str, transport=None):
    with factory.begin() as session:
        job = session.scalar(select(m.Job).where(m.Job.id == job_id).with_for_update())
        if job is None or job.lease_token != token or job.status != "leased":
            return
        run = session.get(m.Run, job.run_id)
        # An interrupted external request cannot be assumed unsent. Preserve it as such.
        for old in session.scalars(
            select(m.ModelCall).where(
                m.ModelCall.run_id == run.id,
                m.ModelCall.status == "pending",
                m.ModelCall.purpose
                == (
                    "selected_deviation"
                    if job.kind == "finding_interpretation"
                    else "initial_role_hypotheses"
                ),
            )
        ):
            old.status, old.error, old.completed_at = (
                "interrupted",
                "Request outcome unknown after worker interruption.",
                now(),
            )
        report = ReportView.model_validate(run.report)
        selected = None
        if job.kind == "finding_interpretation":
            selected = session.scalar(
                select(m.Finding)
                .where(m.Finding.run_id == run.id, m.Finding.category == "deviation")
                .order_by(m.Finding.batch_index, m.Finding.id)
                .limit(1)
            )
            profile = session.get(m.Evidence, selected.evidence_ids[1])
            report = report.model_copy(
                update={
                    "profiles": [ChannelProfile.model_validate(profile.details)],
                    "correlations": [],
                }
            )
        summary = providers.summarize(report)
        if selected:
            d = selected.details
            summary.selected_findings = [
                providers.DerivedDeviation(
                    channel_id=d["channel_id"],
                    reference_evidence_id=selected.evidence_ids[0],
                    reference_median=d["reference_median"],
                    reference_scale=d["scale"],
                    score=d["score"],
                    threshold=d["threshold"],
                )
            ]
        payload = providers.request_payload(summary, settings.llm_model)
        call = m.ModelCall(
            run_id=run.id,
            endpoint=settings.llm_endpoint,
            model=settings.llm_model,
            purpose="selected_deviation" if selected else "initial_role_hypotheses",
            status="pending",
            request=payload,
        )
        session.add(call)
        session.flush()
        call_id, run_id = call.id, run.id
        selected_id, batch_index = (selected.id, selected.batch_index) if selected else (None, 0)
        event(session, run.id, "model.requested", {"call_id": call.id, "purpose": call.purpose})
    outcome = providers.invoke(settings, summary, payload, transport)
    with factory.begin() as session:
        run = session.scalar(select(m.Run).where(m.Run.id == run_id).with_for_update())
        job = session.scalar(select(m.Job).where(m.Job.id == job_id).with_for_update())
        call = session.get(m.ModelCall, call_id)
        call.status, call.response, call.error, call.completed_at = (
            outcome.status,
            outcome.response,
            outcome.error,
            now(),
        )
        event(session, run.id, "model.completed", {"call_id": call.id, "status": call.status})
        if job.lease_token != token or job.status != "leased":
            return
        updated = dict(run.report)
        updated["interpretation_status"] = (
            "available" if outcome.status == "succeeded" else "unavailable"
        )
        updated["interpretation_message"] = (
            "Model hypotheses cite computed evidence. Physical roles remain uncertain."
            if outcome.status == "succeeded"
            else outcome.error
        )
        if selected_id is None:
            run.report = updated
        if outcome.interpretation:
            for h in outcome.interpretation.hypotheses:
                session.add(
                    m.Finding(
                        run_id=run.id,
                        batch_index=batch_index,
                        category="interpretation",
                        title=h.role,
                        explanation=h.explanation,
                        confidence=h.confidence,
                        channel_ids=[h.channel_id],
                        evidence_ids=h.evidence_ids,
                        details={
                            "assumptions": h.assumptions,
                            "model_call_id": call_id,
                            "related_finding_id": selected_id,
                        },
                    )
                )
        job.status, job.lease_token, job.lease_until = "done", None, None


def fail_job(factory, job_id: str, token: str, message: str):
    with factory.begin() as session:
        job = session.get(m.Job, job_id)
        if job is None:
            return
        run = session.scalar(select(m.Run).where(m.Run.id == job.run_id).with_for_update())
        session.refresh(job, with_for_update=True)
        if job.lease_token != token:
            return
        job.status = "done"
        if job.kind == "replay":
            run.status, run.error = "failed", message
        elif run.report and job.kind == "interpretation":
            run.report = {
                **run.report,
                "interpretation_status": "unavailable",
                "interpretation_message": message,
            }
        event(session, run.id, "job.failed", {"kind": job.kind, "message": message})
