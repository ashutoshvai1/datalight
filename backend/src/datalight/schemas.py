from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ChannelLimit(Contract):
    minimum: float | None = Field(default=None, allow_inf_nan=False)
    maximum: float | None = Field(default=None, allow_inf_nan=False)

    @model_validator(mode="after")
    def ordered(self):
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("Minimum must not exceed maximum.")
        return self


class MonitoringRule(Contract):
    id: str
    version: Literal[1] = 1
    channel_id: str
    operator: Literal["gt", "gte", "lt", "lte", "outside", "missing"]
    threshold: float | None = Field(default=None, allow_inf_nan=False)
    minimum: float | None = Field(default=None, allow_inf_nan=False)
    maximum: float | None = Field(default=None, allow_inf_nan=False)
    effect: Literal["fault", "quality_warning"] = "quality_warning"

    @model_validator(mode="after")
    def operands(self):
        if self.operator in ("gt", "gte", "lt", "lte"):
            if self.threshold is None or self.minimum is not None or self.maximum is not None:
                raise ValueError("Comparison rules require only a threshold.")
        elif self.operator == "outside":
            if (
                self.minimum is None
                or self.maximum is None
                or self.minimum > self.maximum
                or self.threshold is not None
            ):
                raise ValueError("Range rules require ordered minimum and maximum bounds.")
        elif any(v is not None for v in (self.threshold, self.minimum, self.maximum)):
            raise ValueError("Missing-value rules do not take numeric operands.")
        return self


class RuleInterval(Contract):
    row_start: int
    row_end: int


class RuleMatch(Contract):
    rule_id: str
    version: int = 1
    channel_id: str
    effect: Literal["fault", "quality_warning"]
    violation_count: int
    row_start: int
    row_end: int
    evidence_ids: list[str]
    intervals: list[RuleInterval] = Field(default_factory=list)


class MonitoringConfig(Contract):
    excluded_channel_ids: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)


class RuleProposalCreate(Contract):
    request: str = Field(min_length=1, max_length=4000)


class RuleProposalView(Contract):
    id: str
    status: str
    rule: MonitoringRule | None = None
    message: str = ""


class RunConfig(Contract):
    initial_rows: int = Field(default=500, ge=32, le=10000)
    batch_rows: int = Field(default=100, ge=1, le=10000)
    interval: float = Field(default=10, ge=0, le=3600)
    threshold: float = Field(default=6, gt=0, le=100)
    analysis_version: str = "monitor-v2"
    path: str | None = None
    source_id: str | None = None
    reader_mode: Literal["legacy", "rows"] = "legacy"
    excluded_channel_ids: list[str] = Field(default_factory=list)
    rules: list[MonitoringRule] = Field(default_factory=list)
    monitoring_locked: bool = False
    limits: dict[str, ChannelLimit] = Field(default_factory=dict)


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


class ReferenceMetric(Contract):
    median: float
    scale: float
    count: int


class PredictionMetrics(Contract):
    lookback: int = 10
    horizon: int = 5
    forecasts: int = 0
    mae: float | None = None
    slope_mean: float | None = None
    slope_std: float | None = None
    abrupt: ReferenceMetric | None = None
    drift: ReferenceMetric | None = None
    level: ReferenceMetric | None = None
    hold_threshold: int = 20
    constant: bool = False


class ChannelExplanation(Contract):
    channel_id: str
    text: str
    evidence_ids: list[str]


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


class Trigger(Contract):
    channel_id: str
    kind: Literal["abrupt", "drift", "level"]
    value: float
    reference: float
    scale: float
    threshold: float
    score: float
    row_start: int
    row_end: int
    detected_at: int
    evidence_ids: list[str] = Field(default_factory=list)


class Coverage(Contract):
    assessed: int
    total: int
    limited: bool
    message: str


class ForecastError(Contract):
    mae: float | None
    forecast_errors: int


class ConfidenceBasis(Contract):
    channel_id: str
    kind: Literal["abrupt", "level", "drift", "rule"]
    rule_id: str | None = None
    observed_persistence: int = Field(ge=0)
    required_persistence: int = Field(ge=1)
    reference_count: int | None = None
    reference_usable: bool | None = None
    evaluated_at: int
    evidence_ids: list[str]


class DecisionConfidence(Contract):
    level: Literal["low", "high"]
    policy_version: Literal["evidence-v1"] = "evidence-v1"
    explanation: str
    evidence_ids: list[str]
    basis: ConfidenceBasis


class Decision(Contract):
    status: Literal["OK", "Fault Suspected"]
    explanation: str
    coverage: Coverage
    triggers: list[Trigger]
    rule_matches: list[RuleMatch] = Field(default_factory=list)
    quality_warnings: list[str]
    forecast_errors: dict[str, ForecastError] = Field(default_factory=dict)
    row_start: int
    row_end: int
    confidence: DecisionConfidence | None = None


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
    predictions: dict[str, PredictionMetrics] = Field(default_factory=dict)
    explanations: list[ChannelExplanation] = Field(default_factory=list)


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


class DecisionView(Contract):
    id: str
    batch_index: int
    decision: Decision
    effective_status: Literal["OK", "Fault Suspected"]
    human_assessment: str | None
    created_at: datetime


class SourceChoice(Contract):
    path: str
    name: str


class SourcePreview(Contract):
    path: str
    channels: list[str]


class TracePoint(Contract):
    row: int
    sequence: int
    value: float | None
    forecast: float | None


class TraceView(Contract):
    channel_id: str
    points: list[TracePoint]
    flagged: list[Trigger]
    start_batch: int | None = None
    end_batch: int | None = None
    latest_batch: int | None = None
    row_start: int | None = None
    row_end: int | None = None


class AnswerView(Contract):
    id: str
    review_id: str
    status: str
    text: str
    evidence_ids: list[str]
    created_at: datetime


class EvidenceView(Contract):
    id: str
    run_id: str
    batch_index: int
    kind: str
    details: dict[str, Any]


class ReviewCreate(Contract):
    action: Literal["accept", "question", "override"]
    operator: str = Field(default="Local user", min_length=1, max_length=100)
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
