import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import select

from datalight import models as m
from datalight import service, temporal
from datalight.api import create_app
from datalight.ingestion import Window
from datalight.schemas import ChannelLimit


def window(values, segments=None):
    return Window(
        ["x"], [[str(v)] for v in values], segments or [0] * len(values), 0, 0, None, True
    )


def test_linear_forecast_alignment_and_no_future_leakage():
    values = np.arange(120) * 3.0 + 2
    data = window(values)
    model = temporal.baseline(data, [("c001", "x")], {})["c001"]
    assert model.slope_mean == 3 and model.slope_std == 0
    assert model.mae < 1e-12
    features = temporal.features(values, np.zeros(len(values)))
    assert np.isnan(features["forecast"][13]) and features["forecast"][14] == values[14]
    altered = values.copy()
    altered[70:] += 1000
    other = temporal.features(altered, np.zeros(len(values)))
    np.testing.assert_equal(features["forecast"][:75], other["forecast"][:75])


def test_noise_step_drift_constant_and_quality():
    rng = np.random.default_rng(123)
    initial = rng.normal(0, 0.1, 500)
    models = temporal.baseline(window(initial), [("c001", "x")], {})
    for tail, expected in (
        (rng.normal(0, 0.1, 300), None),
        (rng.normal(5, 0.1, 300), "abrupt"),
        (np.arange(300) * 0.08 + rng.normal(0, 0.1, 300), "drift"),
    ):
        values = np.concatenate([initial, tail])
        result = temporal.evaluate(
            window(values), [("c001", "x")], {}, models, "test", skip=500, start_row=501
        )
        kinds = {t.kind for t in result[0]}
        assert (expected in kinds) if expected else not kinds
    constant = window([4.0] * 500)
    models = temporal.baseline(constant, [("c001", "x")], {})
    result = temporal.evaluate(constant, [("c001", "x")], {}, models, "test", initial=True)
    assert not result[0] and result[1][1].status == "unavailable"
    assert "Constant" in result[1][1].explanation
    held = np.repeat(rng.normal(size=100), 5)
    models = temporal.baseline(window(held), [("c001", "x")], {})
    assert models["c001"].hold_threshold == 25
    assert (
        temporal.evaluate(window(held), [("c001", "x")], {}, models, "test", initial=True)[1][
            1
        ].status
        == "pass"
    )
    stuck = window(np.concatenate([held, [held[-1]] * 50]))
    assert (
        temporal.evaluate(stuck, [("c001", "x")], {}, models, "test", initial=True)[1][1].status
        == "fail"
    )
    ranges = {"x": ChannelLimit(minimum=-10, maximum=10)}
    values = np.concatenate([held, [float("nan")] * 10, [999.0] * 50])
    result = temporal.evaluate(
        window(values), [("c001", "x")], ranges, models, "test", skip=500, start_row=501
    )
    assert not result[0] and not result[4]
    assert result[1][0].affected == 50


def test_boundaries_gaps_and_short_windows_do_not_bridge():
    values = np.arange(100, dtype=float)
    segments = np.concatenate([np.zeros(50), np.ones(50)])
    features = temporal.features(values, segments)
    assert np.isnan(features["forecast"][50:64]).all()
    assert np.isnan(features["drift"][50:99]).all()
    values[30] = np.nan
    features = temporal.features(values, np.zeros(100))
    assert np.isnan(features["forecast"][30:45]).all()
    assert temporal.baseline(window([1.0] * 10), [("c001", "x")], {})["c001"].mae is None


def test_batch_size_and_restart_do_not_change_triggered_observations(store):
    settings, factory = store
    client = TestClient(create_app(settings, factory))
    results = []
    for batch_rows in (7, 37, 100, 173):
        run = client.post("/api/v1/runs", json={"batch_rows": batch_rows, "interval": 0}).json()
        service.replay(factory, settings, *service.claim(factory, "replay"))
        client.post(f"/api/v1/runs/{run['id']}/control", json={"action": "resume"})
        count = 0
        while job := service.claim(factory, "replay"):
            service.replay(factory, settings, *job)
            count += 1
            if count == 3:
                client.post(f"/api/v1/runs/{run['id']}/control", json={"action": "pause"})
                service.bootstrap(factory, settings)
                assert service.claim(factory, "replay") is None
                client.post(f"/api/v1/runs/{run['id']}/control", json={"action": "resume"})
        with factory() as session:
            findings = session.scalars(
                select(m.Finding).where(
                    m.Finding.run_id == run["id"], m.Finding.category == "decision"
                )
            ).all()
            triggers = {
                (t["channel_id"], t["kind"], row)
                for f in findings
                for t in f.details["triggers"]
                for row in range(
                    t["detected_at"], t["row_end"] + 1, 10 if t["kind"] == "drift" else 1
                )
            }
            results.append(triggers)
            assert session.get(m.Run, run["id"]).rows_processed == 1600
    assert results[0] and all(result == results[0] for result in results)


def test_invalid_order_coordinates_and_record_width_break_forecasts():
    data = Window(
        ["sample", "x"],
        [[str(i + 1), str(i)] for i in range(100)],
        [0] * 100,
        0,
        0,
        100,
        True,
        sample_index=0,
        invalid_records=[False] * 100,
    )
    data.invalid_records[30] = True
    data.rows[60][0] = "invalid"
    values, segments, _ = temporal.vectors(data, "x")
    forecasts = temporal.features(values, segments)["forecast"]
    assert np.isnan(forecasts[30:45]).all()
    assert np.isnan(forecasts[60:75]).all()


def test_evaluation_metadata_cannot_change_temporal_results(dataset, tmp_path):
    import csv

    from datalight import analysis
    from datalight.ingestion import read_window

    with dataset.open() as handle:
        rows = list(csv.reader(handle))
    for row in rows[1:]:
        for name in ("faultNumber", "fault_status", "source", "simulationRun"):
            if name in rows[0]:
                row[rows[0].index(name)] = "evaluation metadata changed"
    changed = tmp_path / "changed.csv"
    with changed.open("w") as handle:
        csv.writer(handle).writerows(rows)
    results = []
    for path in (dataset, changed):
        initial = read_window(path, 0, 500, split_sequences=False)
        full = read_window(path, 0, 1600, split_sequences=False)
        _, channels = analysis.classify(initial)
        models = temporal.baseline(initial, channels, {})
        facts = []
        evaluated = temporal.evaluate(
            full, channels, {}, models, "same-evidence", skip=500, start_row=501,
            confidence_facts=facts, reference_usable=dict.fromkeys((cid for cid, _ in channels), True),
        )
        results.append(
            ([t.model_dump() for t in evaluated[0]], {k: v.model_dump() for k, v in models.items()},
             [f.model_dump() for f in facts])
        )
    assert results[0] == results[1]
