from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class RunConfig(Contract):
    initial_rows: int = Field(default=500, ge=32, le=10000)
    batch_rows: int = Field(default=100, ge=32, le=10000)
    interval: float = Field(default=1, ge=0, le=60)
    threshold: float = Field(default=6, gt=0, le=100)
    analysis_version: str = "foundation-v1"


class RunView(Contract):
    id: str
    source_id: str
    status: str
    config: RunConfig
    rows_processed: int
    batch_index: int
    sequence: int
    fast_forward: bool
    error: str | None
    created_at: datetime


class SourceView(Contract):
    id: str
    name: str
    identity: dict[str, Any]


class SystemView(Contract):
    source: SourceView | None
    run: RunView | None
    source_error: str | None
    model_status: str


class ChannelProfile(Contract):
    id: str
    name: str
    count: int
    valid: int
    missing: int
    invalid: int
    completeness: float
    mean: float | None
    std: float | None
    minimum: float | None
    maximum: float | None
    q05: float | None
    median: float | None
    q95: float | None
    mad: float | None
    difference_std: float | None
    lag1: float | None
    hold_median: float | None
    hold_max: int
    usable: bool
    evidence_id: str


class Correlation(Contract):
    left: str
    right: str
    count: int
    coefficient: float | None
    reason: str | None
    evidence_id: str


class Column(Contract):
    name: str
    role: str
    reason: str


class Check(Contract):
    name: str
    status: Literal["pass", "fail", "unavailable"]
    affected: int
    explanation: str
    evidence_id: str


class ReportView(Contract):
    profiles: list[ChannelProfile]
    correlations: list[Correlation]
    columns: list[Column]
    checks: list[Check]
    limitations: list[str]
    trust: str
    interpretation_status: str
    interpretation_message: str
    reference_version: str


class BatchView(Contract):
    id: int
    index: int
    kind: str
    row_start: int
    row_end: int
    sequence: int
    summary: dict[str, Any]
    created_at: datetime


class FindingView(Contract):
    id: str
    run_id: str
    batch_index: int
    category: str
    title: str
    explanation: str
    confidence: str
    channel_ids: list[str]
    evidence_ids: list[str]
    details: dict[str, Any]
    created_at: datetime


class EvidenceView(Contract):
    id: str
    run_id: str
    batch_index: int
    kind: str
    details: dict[str, Any]


class ReviewCreate(Contract):
    action: Literal["accept", "question", "override"]
    operator: str = Field(min_length=1, max_length=100)
    reason: str = Field(default="", max_length=4000)
    replacement: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def meaningful_text(self):
        if not self.operator.strip():
            raise ValueError("Operator name is required.")
        if self.action != "accept" and not self.reason.strip():
            raise ValueError("Questions and overrides require an explanation.")
        if self.action == "override" and not (self.replacement or "").strip():
            raise ValueError("An override requires a replacement conclusion.")
        return self


class ReviewView(ReviewCreate):
    id: str
    finding_id: str
    created_at: datetime


class EventView(Contract):
    id: int
    run_id: str
    kind: str
    payload: dict[str, Any]
    created_at: datetime


class ModelCallView(Contract):
    id: str
    run_id: str
    endpoint: str
    model: str
    purpose: str
    status: str
    request: dict[str, Any]
    response: dict[str, Any] | None
    error: str | None
    started_at: datetime
    completed_at: datetime | None


class RunControl(Contract):
    action: Literal["pause", "resume", "fast_forward", "normal_speed"]
