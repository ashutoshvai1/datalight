"""Causal sample-window analysis. No labels, names, playback time, or batch-size rules."""

import math

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from . import confidence
from .ingestion import Window, finite
from .schemas import (
    ChannelLimit,
    Check,
    ConfidenceBasis,
    PredictionMetrics,
    ReferenceMetric,
    Trigger,
)

HISTORY = 69


def vectors(window: Window, name: str, limit: ChannelLimit | None = None):
    index = window.header.index(name)
    values = np.array([finite(row[index]) for row in window.rows], dtype=float)
    outside = np.zeros(len(values), dtype=bool)
    if limit:
        if limit.minimum is not None:
            outside |= values < limit.minimum
        if limit.maximum is not None:
            outside |= values > limit.maximum
    values[outside] = np.nan
    if window.invalid_records:
        values[np.asarray(window.invalid_records, dtype=bool)] = np.nan
    segments = np.asarray(window.segments).copy()
    # Gaps, duplicates and malformed sample coordinates break temporal windows.
    if window.sample_index is not None:
        samples = [finite(row[window.sample_index]) for row in window.rows]
        group = 0
        for i, value in enumerate(samples):
            if value is None or value < 1 or not value.is_integer():
                values[i] = np.nan
            previous = samples[i - 1] if i else None
            if i and (
                window.segments[i] != window.segments[i - 1]
                or value is None
                or previous is None
                or value != previous + 1
            ):
                group += 1
            segments[i] = group
    return values, segments, int(outside.sum())


def rolling(values, segments, size):
    result = np.full((len(values), size), np.nan)
    if len(values) >= size:
        view = sliding_window_view(values, size)
        good = np.isfinite(view).all(axis=1) & (segments[size - 1 :] == segments[: 1 - size])
        result[size - 1 :][good] = view[good]
    return result


def features(values, segments):
    ten = rolling(values, segments, 10)
    twenty = rolling(values, segments, 20)
    fifty = rolling(values, segments, 50)
    slope = ten @ (np.arange(10) - 4.5) / 82.5
    center = ten.mean(axis=1)
    forecast = np.full(len(values), np.nan)
    errors = []
    for horizon in range(1, 6):
        predicted = center + slope * (4.5 + horizon)
        aligned = np.full(len(values), np.nan)
        if len(values) > horizon:
            good = segments[horizon:] == segments[:-horizon]
            aligned[horizon:] = np.where(good, predicted[:-horizon], np.nan)
            # Every intermediate observation must be valid; do not bridge gaps.
            valid = np.isfinite(rolling(values, segments, horizon + 1)).all(axis=1)
            aligned[~valid] = np.nan
        errors.append(np.abs(aligned - values))
        if horizon == 5:
            forecast = aligned
    return {
        "slope": slope,
        "abrupt": twenty[:, 10:].mean(axis=1) - twenty[:, :10].mean(axis=1),
        "drift": fifty @ (np.arange(50) - 24.5) / 10412.5,
        "level": np.median(ten, axis=1),
        "forecast": forecast,
        "errors": np.stack(errors, axis=1),
    }


def reference(values, tolerance):
    valid = values[np.isfinite(values)]
    if len(valid) < 3:
        return None
    median = float(np.median(valid))
    scale = max(float(1.4826 * np.median(np.abs(valid - median))), float(np.std(valid)), tolerance)
    if not math.isfinite(scale):
        return None
    return ReferenceMetric(median=median, scale=scale, count=len(valid))


def hold_lengths(values, segments):
    completed, length = [], 0
    for i, value in enumerate(values):
        same = i and segments[i] == segments[i - 1] and value == values[i - 1]
        if same and np.isfinite(value):
            length += 1
        else:
            # A hold ending in a value change is complete; boundaries are censored.
            if i and segments[i] == segments[i - 1] and np.isfinite(value) and length:
                completed.append(length)
            length = 1 if np.isfinite(value) else 0
    return completed, length


def baseline(window, channels, limits):
    models = {}
    for cid, name in channels:
        values, segments, _ = vectors(window, name, limits.get(name))
        f = features(values, segments)
        valid = values[np.isfinite(values)]
        slopes = f["slope"][np.isfinite(f["slope"])]
        errors = f["errors"][np.isfinite(f["errors"])]
        completed, _ = hold_lengths(values, segments)
        tolerance = max(1e-12, float(np.max(np.abs(valid))) * 1e-9) if len(valid) else 1e-12
        models[cid] = PredictionMetrics(
            forecasts=len(errors),
            mae=float(errors.mean()) if len(errors) else None,
            slope_mean=float(slopes.mean()) if len(slopes) else None,
            slope_std=float(slopes.std()) if len(slopes) else None,
            abrupt=reference(f["abrupt"], tolerance),
            drift=reference(f["drift"], tolerance),
            level=reference(valid, tolerance),
            hold_threshold=max(20, math.ceil(5 * float(np.median(completed)))) if completed else 20,
            constant=bool(len(valid) and np.ptp(valid) == 0),
        )
    return models


def evaluate(
    window,
    channels,
    limits,
    models,
    prefix,
    start_row=1,
    skip=0,
    state=None,
    initial=False,
    confidence_facts=None,
    reference_usable=None,
):
    """Process new observations only; preceding context is reread from the CSV.

    State contains counters and offsets, never observation values. Prefix context is
    used for causal features, but cannot increment persisted counters a second time.
    """
    state = state or {}
    counters = {}
    triggers: list[Trigger] = []
    checks, metrics = [], {}
    assessed = set()
    for cid, name in channels:
        model = models[cid]
        values, segments, _ = vectors(window, name, limits.get(name))
        _, _, outside = vectors(
            Window(window.header, window.rows[skip:], window.segments[skip:], 0, 0, None, False),
            name,
            limits.get(name),
        )
        f = features(values, segments)
        errors = f["errors"][skip:]
        errors = errors[np.isfinite(errors)]
        metrics[cid] = {
            "mae": float(errors.mean()) if len(errors) else None,
            "forecast_errors": len(errors),
        }
        previous = state.get(cid, {})
        persistence = {k: dict(v) for k, v in previous.get("confidence", {}).items()}
        hold = previous.get("hold", 0)
        streak = previous.get("streak", 0)
        direction = previous.get("direction", 0)
        first_drift = previous.get("first_drift", start_row)
        position = previous.get("position", 0)
        max_hold = 0
        for i in range(skip, len(values)):
            row = start_row + i - skip
            continuous = i > 0 and segments[i] == segments[i - 1]
            if not continuous:
                hold, streak, direction, position = 0, 0, 0, 0
                persistence = {}
            position += 1
            value = values[i]
            if not np.isfinite(value):
                hold, streak, direction = 0, 0, 0
                persistence = {}
                continue
            hold = hold + 1 if continuous and value == values[i - 1] else 1
            max_hold = max(max_hold, hold)
            if initial:
                continue
            for kind in ("abrupt", "level", "drift"):
                ref = getattr(model, kind)
                measured = f[kind][i]
                if ref is None or not np.isfinite(measured):
                    persistence.pop(kind, None)
                    if kind == "drift":
                        streak, direction = 0, 0
                    continue
                if kind == "drift" and model.abrupt is not None and model.level is not None:
                    assessed.add(cid)
                score = float((measured - ref.median) / ref.scale)
                if kind == "drift":
                    if position % 10:
                        continue
                    sign = 1 if score > 6 else -1 if score < -6 else 0
                    if sign and sign == direction:
                        streak += 1
                    else:
                        streak, first_drift = int(bool(sign)), row - 49
                    direction = sign
                    if streak < 3:
                        continue
                else:
                    sign = 1 if score > 6 else -1 if score < -6 else 0
                    prior_count = persistence.get(kind, {})
                    count = (
                        prior_count.get("count", 0) + 1
                        if sign and sign == prior_count.get("direction")
                        else int(bool(sign))
                    )
                    persistence[kind] = {"count": count, "direction": sign}
                    if not sign:
                        continue
                if confidence_facts is not None:
                    confidence.retain(
                        confidence_facts,
                        ConfidenceBasis(
                            channel_id=cid,
                            kind=kind,
                            observed_persistence=streak
                            if kind == "drift"
                            else persistence[kind]["count"],
                            required_persistence=3 if kind == "drift" else confidence.PERSISTENCE,
                            reference_count=ref.count,
                            reference_usable=(reference_usable or {}).get(cid, False),
                            evaluated_at=row,
                            evidence_ids=[
                                f"{prefix}:temporal:{cid}",
                                f"{prefix.rsplit(':b', 1)[0]}:b0:temporal:{cid}",
                                f"{prefix.rsplit(':b', 1)[0]}:b0:profile:{cid}",
                            ],
                        ),
                    )
                triggers.append(
                    Trigger(
                        channel_id=cid,
                        kind=kind,
                        value=float(measured),
                        reference=ref.median,
                        scale=ref.scale,
                        threshold=6,
                        score=abs(score),
                        row_start=first_drift
                        if kind == "drift"
                        else row - (19 if kind == "abrupt" else 9),
                        row_end=row,
                        detected_at=row,
                        evidence_ids=[f"{prefix}:temporal:{cid}"],
                    )
                )
        counters[cid] = dict(
            hold=hold,
            streak=streak,
            direction=direction,
            first_drift=first_drift,
            position=position,
            confidence=persistence,
        )
        checks.append(
            Check(
                name=f"range:{cid}",
                status="fail" if outside else "pass" if name in limits else "unavailable",
                affected=outside,
                explanation=f"{outside} values outside configured limits."
                if name in limits
                else "Not configured.",
                evidence_id=f"{prefix}:range:{cid}",
            )
        )
        frozen = max_hold >= model.hold_threshold and not model.constant
        checks.append(
            Check(
                name=f"frozen:{cid}",
                status="unavailable" if model.constant else "fail" if frozen else "pass",
                affected=int(frozen),
                explanation="Constant; stuck cannot be established."
                if model.constant
                else f"Longest hold {max_hold} samples; warning threshold {model.hold_threshold}.",
                evidence_id=f"{prefix}:frozen:{cid}",
            )
        )
    # Consecutive alarms are represented as compact intervals, retaining strongest evidence.
    compact: list[Trigger] = []
    for trigger in triggers:
        prior = next(
            (
                t
                for t in reversed(compact)
                if t.channel_id == trigger.channel_id and t.kind == trigger.kind
            ),
            None,
        )
        if prior and trigger.row_end - prior.row_end <= (10 if trigger.kind == "drift" else 1):
            prior.row_end = trigger.row_end
            if trigger.score > prior.score:
                prior.value, prior.score = trigger.value, trigger.score
        else:
            compact.append(trigger)
    return compact, checks, counters, metrics, assessed
