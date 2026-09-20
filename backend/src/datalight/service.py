"""Transactional replay and independently queued interpretation. Raw data stays in the CSV."""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import and_, or_, select, text

from . import analysis, providers, rules, sources, temporal
from . import models as m
from .db import now
from .ingestion import SourceError, fingerprint, identity, read_window
from .schemas import ChannelExplanation, Check, Coverage, Decision, ReportView, RunConfig, Trigger


def event(session, run_id, kind, payload):
    session.add(m.AuditEvent(run_id=run_id, kind=kind, payload=payload))


def coordination_lock(session):
    if session.bind.dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(724901)"))


def create_run(session, source, config):
    run = m.Run(source_id=source.id, config=config.model_dump())
    session.add(run)
    session.flush()
    session.add(m.Job(run_id=run.id, kind="replay"))
    event(session, run.id, "run.created", {"config": config.model_dump(), "source_id": source.id})
    return run


def register_source(session, settings, path=None):
    path = sources.resolve(settings, path)
    info = identity(path)
    digest = fingerprint(info)
    source = session.scalar(select(m.Source).where(m.Source.fingerprint == digest))
    if source is None:
        source = m.Source(identity=info, fingerprint=digest, name=path.name, path=str(path))
        session.add(source)
        session.flush()
    elif source.path is None:
        source.path = str(path)
    return source


def bootstrap(factory, settings):
    # Startup never creates an analysis. Explicit POST /runs is the only entry point.
    return None


def source_path(source, settings):
    path = sources.resolve(settings, source.path or str(settings.data_path))
    if identity(path) != source.identity:
        raise SourceError("CSV changed since this analysis began. Start a new analysis.")
    return path


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


def context_window(path, window, state, reader_mode="legacy"):
    history = state.get("history") if state else None
    if not history:
        return window, 0
    prior = read_window(
        path,
        history["cursor"],
        history["count"],
        sequence=history["sequence"],
        split_sequences=False,
        reader_mode=reader_mode,
    )
    skip = len(prior.rows)
    prior.rows += window.rows
    prior.segments += window.segments
    prior.offsets += window.offsets
    prior.invalid_records += window.invalid_records
    return prior, skip


def replay(factory, settings, job_id, token):
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
        path = source_path(source, settings)
        config = RunConfig.model_validate(run.config)
        initial = run.report is None
        window = read_window(
            path,
            run.cursor,
            config.initial_rows if initial else config.batch_rows,
            run.last_sample,
            run.sequence,
            split_sequences=not initial,
            reader_mode=config.reader_mode,
        )
        if not window.rows:
            if initial:
                raise SourceError("CSV has a header but contains no observations.")
            run.status, job.status = "completed", "done"
            return
        prefix = f"{run.id}:b{run.batch_index}"
        if initial:
            columns, channels = analysis.classify(window)
            if not channels:
                raise SourceError("No numeric channels found in the initial window.")
            unknown = set(config.limits) - {name for _, name in channels}
            if unknown:
                raise SourceError("A configured limit does not match a numeric channel.")
        else:
            channels = [
                (p["id"], p["name"])
                for p in run.report["profiles"]
                if p["id"] not in config.excluded_channel_ids
            ]
        current, vectors = analysis.profiles(window, channels, prefix)
        checks, trust = analysis.quality(window, current, prefix)
        checks = [
            c
            for c in checks
            if c.name not in ("physical_range", "units", "timeliness", "stuck_sensor")
        ]
        pairs = analysis.correlations(vectors, prefix) if initial else []
        state = run.detector_state or {}
        combined, skip = context_window(path, window, state, config.reader_mode)
        if initial:
            models = temporal.baseline(window, channels, config.limits)
        else:
            report = ReportView.model_validate(run.report)
            models = report.predictions
            if not models:
                raise SourceError(
                    "This historical analysis uses an older detector. Start a new analysis to monitor."
                )
        triggers, extra, counters, metrics, assessed = temporal.evaluate(
            combined,
            channels,
            config.limits,
            models,
            prefix,
            run.rows_processed + 1,
            skip,
            state.get("channels"),
            initial,
        )
        checks += extra
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
            session.add(
                m.Evidence(
                    id=f"{prefix}:temporal:{p.id}",
                    run_id=run.id,
                    batch_index=run.batch_index,
                    kind="temporal",
                    details={
                        "channel_id": p.id,
                        "reference": models[p.id].model_dump(),
                        "current": metrics[p.id],
                        "triggers": [t.model_dump() for t in triggers if t.channel_id == p.id],
                        "reference_evidence_id": f"{run.id}:b0:temporal:{p.id}",
                    },
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
        for pair in pairs:
            session.add(
                m.Evidence(
                    id=pair.evidence_id,
                    run_id=run.id,
                    batch_index=0,
                    kind="correlation",
                    details=pair.model_dump(),
                )
            )
        quality_warnings = [f"{c.name}: {c.explanation}" for c in checks if c.status == "fail"]
        rule_matches = (
            []
            if initial
            else rules.evaluate(window, channels, config.rules, prefix, run.rows_processed + 1)
        )
        rule_lookup = {rule.id: rule for rule in config.rules}
        for match in rule_matches:
            session.add(
                m.Evidence(
                    id=match.evidence_ids[0],
                    run_id=run.id,
                    batch_index=run.batch_index,
                    kind="rule",
                    details={
                        "rule": rule_lookup[match.rule_id].model_dump(),
                        "match": match.model_dump(),
                    },
                )
            )
            if match.effect == "quality_warning":
                quality_warnings.append(
                    f"User rule {match.rule_id}: {match.violation_count} observations matched."
                )
        if initial:
            reason = settings.interpretation_unavailable
            report = ReportView(
                profiles=current,
                correlations=pairs,
                columns=columns,
                checks=checks,
                limitations=[
                    "The initial window is a provisional reference, not proof of healthy operation.",
                    "Slopes use channel units per sample; playback seconds are not sampling time.",
                    "Correlation is association, not causation. Quality warnings are separate from process decisions.",
                ],
                trust=trust,
                interpretation_status="unavailable" if reason else "pending",
                interpretation_message=reason or "Channel explanations are being prepared.",
                reference_version=f"{run.id}:reference-v2",
                predictions=models,
            )
            run.report = report.model_dump()
            if not reason:
                for start in range(0, len(channels), 8):
                    session.add(
                        m.Job(
                            run_id=run.id,
                            kind="interpretation",
                            task_key=f"group-{start // 8}",
                            payload={
                                "channel_ids": [cid for cid, _ in channels[start : start + 8]]
                            },
                        )
                    )
            event(
                session, run.id, "report.created", {"reference_version": report.reference_version}
            )
        else:
            coverage = Coverage(
                assessed=len(assessed),
                total=len(channels),
                limited=len(assessed) < len(channels),
                message="Insufficient usable data—process assessment limited"
                if len(assessed) < len(channels)
                else "All channels assessed.",
            )
            strongest = sorted(triggers, key=lambda t: t.score, reverse=True)[:3]
            names = dict(channels)
            explanation = "; ".join(
                f"{names[t.channel_id]}: {t.kind} change, {t.value:.5g} versus reference {t.reference:.5g} ({t.score:.1f} scales; threshold 6)"
                for t in strongest
            )
            fault_rules = [match for match in rule_matches if match.effect == "fault"]
            if fault_rules:
                explanation = "; ".join(
                    filter(
                        None,
                        [
                            explanation,
                            *[
                                f"{names[match.channel_id]}: applied fault rule matched {match.violation_count} observations"
                                for match in fault_rules
                            ],
                        ],
                    )
                )
            decision = Decision(
                status="Fault Suspected" if triggers or fault_rules else "OK",
                explanation=(explanation + ". This is a detected change, not a diagnosis.")
                if triggers or fault_rules
                else "No process-change rule triggered.",
                coverage=coverage,
                triggers=triggers,
                rule_matches=rule_matches,
                quality_warnings=quality_warnings,
                forecast_errors=metrics,
                row_start=run.rows_processed + 1,
                row_end=run.rows_processed + len(window.rows),
            )
            decision_evidence = f"{prefix}:decision"
            session.add(
                m.Evidence(
                    id=decision_evidence,
                    run_id=run.id,
                    batch_index=run.batch_index,
                    kind="decision",
                    details=decision.model_dump(),
                )
            )
            session.add(
                m.Finding(
                    run_id=run.id,
                    batch_index=run.batch_index,
                    category="decision",
                    title=decision.status,
                    explanation=decision.explanation,
                    confidence="measured",
                    channel_ids=sorted(
                        {t.channel_id for t in triggers} | {t.channel_id for t in rule_matches}
                    ),
                    evidence_ids=[decision_evidence]
                    + [f"{prefix}:temporal:{cid}" for cid, _ in channels]
                    + [c.evidence_id for c in checks if c.status == "fail"]
                    + [match.evidence_ids[0] for match in rule_matches],
                    details=decision.model_dump(),
                )
            )
        start = max(0, len(combined.rows) - temporal.HISTORY)
        run.detector_state = {
            "channels": counters,
            "history": {
                "cursor": combined.offsets[start],
                "count": len(combined.rows) - start,
                "sequence": combined.segments[start],
            },
        }
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
                    "metrics": metrics,
                    "start_offset": run.cursor,
                    "end_offset": window.cursor,
                    "start_sequence": window.segments[0],
                    "deviations": len(triggers),
                },
            )
        )
        event(
            session,
            run.id,
            "batch.committed",
            {"batch_index": run.batch_index, "row_start": row_start, "row_end": run.rows_processed},
        )
        run.cursor, run.sequence, run.last_sample = (
            window.cursor,
            window.sequence,
            window.last_sample,
        )
        run.batch_index += 1
        run.status = "completed" if window.eof else "paused" if initial else "running"
        job.status = "done" if window.eof else "queued"
        job.lease_token, job.lease_until = None, None
        job.available_at = now() + timedelta(seconds=0 if run.fast_forward else config.interval)


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
        elif job.kind == "rule_proposal":
            job.payload = {
                **job.payload,
                "result": {
                    "id": job.task_key,
                    "status": "failed",
                    "rule": None,
                    "message": message,
                },
            }
        elif job.kind == "question":
            session.add(
                m.Answer(
                    review_id=job.payload["review_id"],
                    status="failed",
                    text=message,
                    evidence_ids=[],
                )
            )
        elif run.report and job.kind == "interpretation":
            run.report = {
                **run.report,
                "interpretation_status": "unavailable",
                "interpretation_message": message,
            }
        event(session, run.id, "job.failed", {"kind": job.kind, "message": message})


def interpret(factory, settings, job_id, token, transport=None):
    with factory.begin() as session:
        job = session.scalar(select(m.Job).where(m.Job.id == job_id).with_for_update())
        if job is None or job.lease_token != token or job.status != "leased":
            return
        run = session.get(m.Run, job.run_id)
        report = ReportView.model_validate(run.report)
        data = job.payload or {}
        purpose = f"{job.kind}:{job.task_key}"
        for old in session.scalars(
            select(m.ModelCall).where(
                m.ModelCall.run_id == run.id,
                m.ModelCall.purpose == purpose,
                m.ModelCall.status == "pending",
            )
        ):
            old.status, old.error, old.completed_at = (
                "interrupted",
                "Outcome unknown after worker interruption.",
                now(),
            )
        review = None
        if job.kind == "question":
            review = session.get(m.Review, data["review_id"])
            finding = session.get(m.Finding, review.finding_id)
            decision = Decision.model_validate(finding.details)
            question = data.get("question") or providers.question_text(review.reason, report, settings)
            excluded = set(run.config.get("excluded_channel_ids", []))
            # Keep the original report for privacy sanitization above; only monitored
            # channels and relationships enter the decision's model context.
            report = report.model_copy(update={
                "profiles": [p for p in report.profiles if p.id not in excluded],
                "correlations": [
                    pair for pair in report.correlations
                    if pair.left not in excluded and pair.right not in excluded
                ],
            })
            targets = sorted(
                ({t.channel_id for t in decision.triggers}
                 | {match.channel_id for match in decision.rule_matches}) - excluded
            ) or [p.id for p in report.profiles]
            summary = providers.summarize(report, targets)
            selected: dict[tuple[str, str], Trigger] = {}
            for trigger in decision.triggers:
                if trigger.channel_id in excluded:
                    continue
                key = (trigger.channel_id, trigger.kind)
                if key not in selected or trigger.score > selected[key].score:
                    selected[key] = trigger
            decision_evidence = f"{run.id}:b{finding.batch_index}:decision"
            if session.get(m.Evidence, decision_evidence) is None:
                # Compatibility for already-stored v2 decisions from before decision citations.
                session.add(
                    m.Evidence(
                        id=decision_evidence,
                        run_id=run.id,
                        batch_index=finding.batch_index,
                        kind="decision",
                        details=decision.model_dump(),
                    )
                )
            summary.decision = providers.DerivedDecision(
                evidence_id=decision_evidence,
                status=decision.status,
                assessed=decision.coverage.assessed,
                total=decision.coverage.total,
                evidence_ids=list(dict.fromkeys([decision_evidence, *finding.evidence_ids])),
                forecast_errors={
                    cid: metric for cid, metric in decision.forecast_errors.items()
                    if cid not in excluded
                },
                rule_evidence=[
                    providers.DerivedRuleEvidence(
                        rule=e.details["rule"],
                        violation_count=e.details["match"]["violation_count"],
                        evidence_id=e.id,
                    )
                    for eid in finding.evidence_ids
                    if (e := session.get(m.Evidence, eid)) and e.kind == "rule"
                    and e.details["rule"]["channel_id"] not in excluded
                ],
                quality_checks=[
                    Check.model_validate(e.details)
                    for eid in finding.evidence_ids
                    if (e := session.get(m.Evidence, eid)) and e.kind == "quality"
                    and e.details.get("name", "").split(":")[-1] not in excluded
                ],
                triggers=[
                    providers.DerivedTrigger(
                        **t.model_dump(exclude={"row_start", "row_end", "detected_at"})
                    )
                    for t in selected.values()
                ],
            )
            summary.question = question
            summary.conversation = [
                providers.ConversationTurn.model_validate(turn)
                for turn in data.get("conversation", [])
            ]
        else:
            summary = providers.summarize(report, data.get("channel_ids"))
        payload = providers.request_payload(summary, settings.llm_model)
        call = m.ModelCall(
            run_id=run.id,
            endpoint=settings.llm_endpoint,
            model=settings.llm_model,
            purpose=purpose,
            status="pending",
            request=payload,
        )
        session.add(call)
        session.flush()
        call_id, run_id = call.id, run.id
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
        if job.lease_token != token or job.status != "leased":
            return
        if job.kind == "question":
            session.add(
                m.Answer(
                    review_id=data["review_id"],
                    status=outcome.status,
                    text=outcome.answer.text
                    if outcome.answer
                    else outcome.error or "Answer unavailable.",
                    evidence_ids=outcome.answer.evidence_ids if outcome.answer else [],
                )
            )
        else:
            updated = ReportView.model_validate(run.report)
            if outcome.interpretation:
                updated.explanations += [
                    ChannelExplanation.model_validate(e)
                    for e in outcome.interpretation.explanations
                ]
            remaining = session.scalar(
                select(m.Job.id)
                .where(
                    m.Job.run_id == run.id,
                    m.Job.kind == "interpretation",
                    m.Job.id != job.id,
                    m.Job.status.in_(["queued", "leased"]),
                )
                .limit(1)
            )
            updated.interpretation_status = (
                "pending"
                if remaining
                else "available"
                if len(updated.explanations) == len(updated.profiles)
                else "partial"
                if updated.explanations
                else "unavailable"
            )
            updated.interpretation_message = f"{len(updated.explanations)} of {len(updated.profiles)} channel explanations available."
            if outcome.error:
                updated.interpretation_message += " " + outcome.error
            run.report = updated.model_dump()
        job.status, job.lease_token, job.lease_until = "done", None, None
        event(session, run.id, "model.completed", {"call_id": call.id, "status": call.status})
