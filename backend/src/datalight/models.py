from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, now

Json = JSON().with_variant(JSONB, "postgresql")


def uid() -> str:
    return str(uuid4())


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    identity: Mapped[dict[str, Any]] = mapped_column(Json)
    path: Mapped[str | None] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    status: Mapped[str] = mapped_column(String(24), default="initializing")
    config: Mapped[dict[str, Any]] = mapped_column(Json)
    cursor: Mapped[int] = mapped_column(BigInteger, default=0)
    rows_processed: Mapped[int] = mapped_column(default=0)
    batch_index: Mapped[int] = mapped_column(default=0)
    sequence: Mapped[int] = mapped_column(default=0)
    last_sample: Mapped[float | None] = mapped_column(Float)
    report: Mapped[dict[str, Any] | None] = mapped_column(Json)
    detector_state: Mapped[dict[str, Any] | None] = mapped_column(Json)
    fast_forward: Mapped[bool] = mapped_column(default=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("run_id", "kind", "task_key", name="uq_job_task"),
        Index("ix_job_claim", "kind", "status", "available_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    kind: Mapped[str] = mapped_column(String(24))
    task_key: Mapped[str] = mapped_column(String(100), default="main")
    payload: Mapped[dict[str, Any] | None] = mapped_column(Json)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    attempts: Mapped[int] = mapped_column(default=0)


class Batch(Base):
    __tablename__ = "batches"
    __table_args__ = (UniqueConstraint("run_id", "index"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    index: Mapped[int]
    kind: Mapped[str] = mapped_column(String(24))
    row_start: Mapped[int]
    row_end: Mapped[int]
    sequence: Mapped[int]
    summary: Mapped[dict[str, Any]] = mapped_column(Json)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    batch_index: Mapped[int]
    kind: Mapped[str] = mapped_column(String(30))
    details: Mapped[dict[str, Any]] = mapped_column(Json)


class Finding(Base):
    __tablename__ = "findings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    batch_index: Mapped[int]
    category: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(String(255))
    explanation: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(24))
    channel_ids: Mapped[list[str]] = mapped_column(Json)
    evidence_ids: Mapped[list[str]] = mapped_column(Json)
    details: Mapped[dict[str, Any]] = mapped_column(Json)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id"), index=True)
    action: Mapped[str] = mapped_column(String(24))
    operator: Mapped[str] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(Text)
    replacement: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict[str, Any]] = mapped_column(Json)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ModelCall(Base):
    __tablename__ = "model_calls"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    endpoint: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(255))
    purpose: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(24))
    request: Mapped[dict[str, Any]] = mapped_column(Json)
    response: Mapped[dict[str, Any] | None] = mapped_column(Json)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Answer(Base):
    __tablename__ = "answers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id"), unique=True)
    status: Mapped[str] = mapped_column(String(24))
    text: Mapped[str] = mapped_column(Text)
    evidence_ids: Mapped[list[str]] = mapped_column(Json)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
