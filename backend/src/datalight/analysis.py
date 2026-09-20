"""Pure deterministic analysis; no HTTP, database, provider, or evaluation labels."""

import itertools
import math

import numpy as np

from .ingestion import Window, finite
from .schemas import ChannelProfile, Check, Column, Correlation

MIN_OBSERVATIONS = 32
MAX_INVALID_FRACTION = 0.05
LIMITATIONS = [
    "The initial window is a provisional reference, not proof of healthy operation.",
    "Correlations describe association, not causal direction or physical identity.",
    "Sample indices are ordering coordinates; timestamps, units, and sampling intervals are unknown.",
    "Physical limits, unit consistency, lag analysis, clustering, gradual drift, and fault classification are not implemented in this foundation.",
    "Stuck-sensor checks are unavailable: regular sample-and-hold behavior must not be treated as failure.",
    "A reset to sample 1 starts a new sequence. Other backward steps are quality failures.",
]


def safe(value) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def classify(window: Window) -> tuple[list[Column], list[tuple[str, str]]]:
    columns = [
        Column(
            name=n,
            role="excluded",
            reason="Evaluation metadata; never used in analysis or model prompts.",
        )
        for n in window.excluded_columns
    ]
    channels: list[tuple[str, str]] = []
    for index, name in enumerate(window.header):
        if index == window.sample_index or name.strip().casefold() == "sample":
            columns.append(
                Column(name=name, role="sequence", reason="Ordering only, not a detector feature.")
            )
            continue
        values = [r[index] for r in window.rows if r[index].strip()]
        numeric = 0
        for value in values:
            try:
                float(value)
                numeric += 1
            except ValueError:
                pass
        if not values or numeric / len(values) >= 0.8:
            channels.append((f"c{len(channels) + 1:03}", name))
            columns.append(
                Column(
                    name=name,
                    role="numeric",
                    reason="Numeric candidate inferred from the initial window; no physical role assumed.",
                )
            )
        else:
            columns.append(
                Column(
                    name=name,
                    role="unsupported",
                    reason="Non-numeric column; retained in schema, not used by the numeric detector.",
                )
            )
    return columns, channels


def profiles(window: Window, channels: list[tuple[str, str]], prefix: str):
    result = []
    vectors = {}
    for channel_id, name in channels:
        index = window.header.index(name)
        raw = [r[index] for r in window.rows]
        values = np.array(
            [finite(x) if finite(x) is not None else np.nan for x in raw], dtype=float
        )
        valid = values[np.isfinite(values)]
        vectors[channel_id] = values
        count = len(values)
        missing = sum(not x.strip() for x in raw)
        invalid = count - len(valid) - missing
        adjacent = np.array([a == b for a, b in itertools.pairwise(window.segments)], dtype=bool)
        if len(values) > 1:
            adjacent &= np.isfinite(values[:-1]) & np.isfinite(values[1:])
        diffs = np.diff(values)[adjacent] if len(values) > 1 else np.array([])
        runs: list[int] = []
        stretch = 0
        for i, value in enumerate(values):
            if not np.isfinite(value):
                if stretch:
                    runs.append(stretch)
                stretch = 0
            elif i and adjacent[i - 1] and value == values[i - 1]:
                stretch += 1
            else:
                if stretch:
                    runs.append(stretch)
                stretch = 1
        if stretch:
            runs.append(stretch)
        median = safe(np.median(valid)) if len(valid) else None
        lag = None
        if adjacent.sum() >= 3:
            left, right = values[:-1][adjacent], values[1:][adjacent]
            if np.std(left) > 0 and np.std(right) > 0:
                lag = safe(np.corrcoef(left, right)[0, 1])
        with np.errstate(over="ignore", invalid="ignore"):
            result.append(
                ChannelProfile(
                    id=channel_id,
                    name=name,
                    count=count,
                    valid=len(valid),
                    missing=missing,
                    invalid=invalid,
                    completeness=len(valid) / count if count else 0,
                    mean=safe(np.mean(valid)) if len(valid) else None,
                    std=safe(np.std(valid)) if len(valid) else None,
                    minimum=safe(np.min(valid)) if len(valid) else None,
                    maximum=safe(np.max(valid)) if len(valid) else None,
                    q05=safe(np.quantile(valid, 0.05)) if len(valid) else None,
                    median=median,
                    q95=safe(np.quantile(valid, 0.95)) if len(valid) else None,
                    mad=safe(np.median(np.abs(valid - median))) if median is not None else None,
                    difference_std=safe(np.std(diffs)) if len(diffs) else None,
                    lag1=lag,
                    hold_median=safe(np.median(runs)) if runs else None,
                    hold_max=max(runs, default=0),
                    usable=len(valid) >= MIN_OBSERVATIONS
                    and (missing + invalid) / max(count, 1) <= MAX_INVALID_FRACTION
                    and window.schema_errors == 0,
                    evidence_id=f"{prefix}:profile:{channel_id}",
                )
            )
    return result, vectors


def correlations(vectors: dict[str, np.ndarray], prefix: str) -> list[Correlation]:
    result = []
    for (left, a), (right, b) in itertools.combinations(vectors.items(), 2):
        mask = np.isfinite(a) & np.isfinite(b)
        count = int(mask.sum())
        value = None
        reason = None
        if count < 3:
            reason = "Fewer than three paired observations."
        elif np.std(a[mask]) == 0 or np.std(b[mask]) == 0:
            reason = "A channel has zero variance."
        else:
            with np.errstate(over="ignore", invalid="ignore"):
                value = safe(np.corrcoef(a[mask], b[mask])[0, 1])
            if value is None:
                reason = "Numerically undefined."
        result.append(
            Correlation(
                left=left,
                right=right,
                count=count,
                coefficient=value,
                reason=reason,
                evidence_id=f"{prefix}:corr:{left}:{right}",
            )
        )
    return result


def quality(window: Window, channel_profiles: list[ChannelProfile], prefix: str):
    checks = []
    specifications = [
        ("completeness", sum(p.missing for p in channel_profiles), "Missing numeric observations."),
        (
            "validity",
            sum(p.invalid for p in channel_profiles),
            "Non-finite or unparseable numeric observations.",
        ),
        ("schema", window.schema_errors, "Records with a different field count from the header."),
        ("sequence_gaps", window.gaps, "Forward gaps in sample indices within a sequence."),
        ("sequence_duplicates", window.duplicates, "Repeated sample indices within a sequence."),
        (
            "sequence_order",
            window.reversed_samples + window.invalid_samples,
            "Invalid or backward sample indices, excluding resets to 1.",
        ),
    ]
    for name, count, explanation in specifications:
        unavailable = name.startswith("sequence_") and window.sample_index is None
        checks.append(
            Check(
                name=name,
                status="unavailable" if unavailable else "fail" if count else "pass",
                affected=count,
                explanation="No sample coordinate supplied." if unavailable else explanation,
                evidence_id=f"{prefix}:quality:{name}",
            )
        )
    for name, explanation in [
        ("physical_range", "Physical limits require an explicit operating rule."),
        ("units", "Units have not been established."),
        ("timeliness", "Real timestamps and an expected delivery schedule are unavailable."),
        (
            "stuck_sensor",
            "Update cadence is profiled, but a validated stuck-sensor rule is not yet available.",
        ),
    ]:
        checks.append(
            Check(
                name=name,
                status="unavailable",
                affected=0,
                explanation=explanation,
                evidence_id=f"{prefix}:quality:{name}",
            )
        )
    usable = sum(p.usable for p in channel_profiles)
    trust = (
        "untrusted"
        if not usable
        else "partial"
        if usable < len(channel_profiles) or any(c.status == "fail" for c in checks)
        else "trusted"
    )
    return checks, trust


def detect(current: list[ChannelProfile], baseline: list[ChannelProfile], threshold: float):
    reference = {p.id: p for p in baseline}
    deviations = []
    unsupported = []
    for p in current:
        old = reference[p.id]
        if not p.usable or not old.usable:
            unsupported.append(
                {
                    "channel_id": p.id,
                    "reason": "Insufficient or unreliable observations in the batch or reference.",
                }
            )
            continue
        if old.mad is None or old.mad <= 0 or old.median is None or p.median is None:
            unsupported.append({"channel_id": p.id, "reason": "Zero or undefined reference MAD."})
            continue
        scale = 1.4826 * old.mad
        score = abs(p.median - old.median) / scale
        if not math.isfinite(score):
            unsupported.append({"channel_id": p.id, "reason": "Numerically undefined deviation."})
        elif score > threshold:
            deviations.append(
                {
                    "channel_id": p.id,
                    "score": score,
                    "threshold": threshold,
                    "reference_median": old.median,
                    "batch_median": p.median,
                    "scale": scale,
                    "evidence_ids": [old.evidence_id, p.evidence_id],
                }
            )
    return deviations, unsupported
