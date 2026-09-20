"""Confidence is persistent evidence strength, never a change to fault detection."""

import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from datalight import confidence, rules, service, temporal
from datalight import models as m
from datalight.api import create_app
from datalight.ingestion import Window
from datalight.schemas import Decision, MonitoringRule, PredictionMetrics, ReferenceMetric


def window(values, segments=None):
    return Window(
        ["signal"], [[str(v)] for v in values], segments or [0] * len(values), 0, 0, None, True
    )


def evaluate(values, kind="level", *, skip=50, state=None, count=50, usable=True, segments=None):
    model = PredictionMetrics(**{kind: ReferenceMetric(median=0, scale=1, count=count)})
    facts = []
    result = temporal.evaluate(
        window(values, segments),
        [("c001", "signal")],
        {},
        {"c001": model},
        "run:b1",
        skip=skip,
        start_row=skip + 1,
        state=state,
        confidence_facts=facts,
        reference_usable={"c001": usable},
    )
    return confidence.assess(facts), result, facts


@pytest.mark.parametrize("kind", ["level", "abrupt"])
def test_nine_to_ten_and_restart(kind):
    # A steep ramp sustains both level and adjacent-mean differences.
    values = np.arange(60) * 10.0
    low, result, _ = evaluate(values[:59], kind)
    assert low.level == "low" and low.basis.observed_persistence == 9
    high, _, _ = evaluate(values, kind, skip=59, state=json.loads(json.dumps(result[2])))
    assert high.level == "high" and high.basis.observed_persistence == 10
    assert high.basis.evaluated_at == 60
    assert high.basis.reference_count == 50
    assert high.policy_version == "evidence-v1"


@pytest.mark.parametrize("count,usable", [(49, True), (50, False)])
def test_reference_gate_does_not_change_detection(count, usable):
    values = [7.0] * 65
    low, result, _ = evaluate(values, count=count, usable=usable)
    high, original, _ = evaluate(values)
    assert low.level == "low" and high.level == "high"
    assert "Limited reference" in low.explanation
    assert result[0] == original[0]


def test_drift_is_high_on_third_existing_check():
    # Position is relative to the processed sequence; checks at rows 60, 70, 80.
    values = np.arange(80) * 10.0
    low, before, _ = evaluate(values[:79], "drift")
    assert low is None and not before[0]
    high, after, _ = evaluate(values, "drift")
    assert high.level == "high" and high.basis.observed_persistence == 3
    assert high.basis.required_persistence == 3 and after[0]


def test_resets_and_strong_one_off_remain_low():
    low, _, _ = evaluate([10000.0] * 51)
    assert low.level == "low"
    _, prior, _ = evaluate([7.0] * 59)
    state = prior[2]
    for values, segments in [
        ([7.0] * 59 + [float("nan")] + [7.0] * 10, None),
        ([7.0] * 70, [0] * 59 + [1] * 11),
        ([7.0] * 59 + [0.0] * 10 + [7.0] * 10, None),
        ([7.0] * 59 + [-7.0] * 10, None),
    ]:
        _, result, _ = evaluate(values, skip=59, state=state, segments=segments)
        assert result[2]["c001"]["confidence"]["level"]["count"] < 10


def test_any_strong_evidence_wins_and_no_signal_returns_none():
    high, _, strong = evaluate([7.0] * 65)
    low, _, weak = evaluate([7.0] * 51, count=3)
    assert confidence.assess(weak + strong).level == high.level == "high"
    assert confidence.assess(weak * 20).level == low.level == "low"
    assert confidence.assess([]) is None


@pytest.mark.parametrize(
    "operator,operands,value",
    [
        ("gt", {"threshold": 1}, 2),
        ("outside", {"minimum": -1, "maximum": 1}, 2),
        ("missing", {}, ""),
    ],
)
def test_rule_persistence_across_batches(operator, operands, value):
    rule = MonitoringRule(id="r1", channel_id="c001", operator=operator, effect="fault", **operands)
    state, facts = {}, []
    rules.evaluate(
        window([value] * 9),
        [("c001", "signal")],
        [rule],
        "run:b1",
        1,
        state=state,
        confidence_facts=facts,
    )
    assert confidence.assess(facts).level == "low"
    facts = []
    rules.evaluate(
        window([value, value]),
        [("c001", "signal")],
        [rule],
        "run:b2",
        10,
        skip=1,
        state=json.loads(json.dumps(state)),
        confidence_facts=facts,
    )
    high = confidence.assess(facts)
    assert high.level == "high" and high.basis.observed_persistence == 10
    assert high.basis.reference_count is None and high.basis.rule_id == "r1"
    facts = []
    rule.effect = "quality_warning"
    assert rules.evaluate(
        window([value] * 20), [("c001", "signal")], [rule], "run:b1", 1, confidence_facts=facts
    )
    assert confidence.assess(facts) is None


@pytest.mark.parametrize(
    "break_kind", ["nonmatch", "invalid", "record", "gap", "duplicate", "reset", "coordinate"]
)
def test_rule_streak_breaks(break_kind):
    data = Window(
        ["sample", "signal"],
        [[str(i + 1), "2"] for i in range(19)],
        [0] * 19,
        0,
        0,
        19,
        True,
        sample_index=0,
        invalid_records=[False] * 19,
    )
    if break_kind == "nonmatch":
        data.rows[9][1] = "0"
    elif break_kind == "invalid":
        data.rows[9][1] = "nan"
    elif break_kind == "record":
        data.invalid_records[9] = True
    elif break_kind == "gap":
        for i in range(9, 19):
            data.rows[i][0] = str(i + 2)
        data.rows.pop()  # Nine observations after the break.
        data.segments.pop()
        data.invalid_records.pop()
    elif break_kind == "duplicate":
        data.rows[9][0] = "9"
    elif break_kind == "reset":
        data.segments[9:] = [1] * 10
        for i in range(9, 19):
            data.rows[i][0] = str(i - 8)
        data.rows.pop()
        data.segments.pop()
        data.invalid_records.pop()
    else:
        data.rows[9][0] = "bad"
    facts = []
    rule = MonitoringRule(id="r1", channel_id="c001", operator="gt", threshold=1, effect="fault")
    rules.evaluate(data, [("c001", "signal")], [rule], "run:b1", 1, confidence_facts=facts)
    assert confidence.assess(facts).level == "low"


def test_confidence_batch_invariance_and_immutable_history(store):
    settings, factory = store
    client = TestClient(create_app(settings, factory))
    results = []
    for batch_rows in (7, 37, 100, 173):
        rid = client.post("/api/v1/runs", json={"batch_rows": batch_rows, "interval": 0}).json()[
            "id"
        ]
        service.replay(factory, settings, *service.claim(factory, "replay"))
        client.post(f"/api/v1/runs/{rid}/control", json={"action": "resume"})
        while job := service.claim(factory, "replay"):
            service.replay(factory, settings, *job)
            # Redelivery cannot increment counters or append decisions twice.
            service.replay(factory, settings, *job)
        with factory() as session:
            run = session.get(m.Run, rid)
            results.append(run.detector_state["channels"])
            findings = session.scalars(select(m.Finding).where(m.Finding.run_id == rid)).all()
            assert any(
                f.details["confidence"] and f.details["confidence"]["level"] == "high"
                for f in findings
            )
            for f in findings:
                d = f.details
                assert (d["confidence"] is not None) == (d["status"] == "Fault Suspected")
                assert f.confidence == "measured"
                e = session.get(m.Evidence, f"{rid}:b{f.batch_index}:decision")
                assert e.details == d
                if d["confidence"]:
                    for eid in d["confidence"]["evidence_ids"]:
                        assert session.get(m.Evidence, eid) is not None
            fault = next(f for f in reversed(findings) if f.details["confidence"])
            original = fault.details
            fid = fault.id
        for action in ("override", "accept"):
            response = client.post(
                f"/api/v1/findings/{fid}/reviews",
                json={
                    "action": action,
                    "reason": "Synthetic review",
                    "replacement": "OK" if action == "override" else None,
                },
            )
            assert response.status_code == 201
        restarted = TestClient(create_app(settings, factory))
        decisions = restarted.get(f"/api/v1/runs/{rid}/decisions?limit=100").json()
        assert next(d for d in decisions if d["id"] == fid)["decision"] == original
        legacy = dict(original)
        legacy.pop("confidence")
        assert Decision.model_validate(legacy).confidence is None
    assert all(r == results[0] for r in results)


def test_constant_reference_is_usable_but_still_needs_persistence():
    initial = window([0.0] * 100)
    models = temporal.baseline(initial, [("c001", "signal")], {})
    facts = []
    temporal.evaluate(
        window([0.0] * 100 + [7.0] * 20),
        [("c001", "signal")],
        {},
        models,
        "run:b1",
        skip=100,
        start_row=101,
        confidence_facts=facts,
        reference_usable={"c001": True},
    )
    assert confidence.assess(facts).level == "high"


@pytest.mark.parametrize("kind", ["level", "abrupt", "drift"])
def test_sample_qualification_points_independent_of_batch_size(monkeypatch, kind):
    original = confidence.retain
    seen = []

    def capture(facts, candidate):
        seen.append((candidate.evaluated_at, confidence.qualifies(candidate)))
        original(facts, candidate)

    monkeypatch.setattr(confidence, "retain", capture)
    values = np.arange(200) * 10.0
    results = []
    for size in (1, 7, 37, 100):
        seen.clear()
        state = None
        for start in range(50, len(values), size):
            _, result, _ = evaluate(values[: start + size], kind, skip=start, state=state)
            state = json.loads(json.dumps(result[2]))
        results.append(list(seen))
    assert results[0] and any(high for _, high in results[0])
    assert all(result == results[0] for result in results)
