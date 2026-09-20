"""Batch-sized chart history must not inherit the legacy 1000-point cap."""

import math

import pytest
from fastapi.testclient import TestClient

from datalight import service
from datalight.api import create_app


def test_large_history_partial_final_batch_and_initial_window(store, tmp_path):
    settings, factory = store
    settings.upload_dir = tmp_path / "uploads"
    client = TestClient(create_app(settings, factory))
    data = "signal\n" + "".join(f"{math.sin(i / 13) + i * 0.001 + (20 if i > 1500 else 0)}\n" for i in range(2707))
    uploaded = client.post(
        "/api/v1/sources/upload", files={"file": ("history.csv", data, "text/csv")}
    )
    assert uploaded.status_code == 201
    created = client.post(
        "/api/v1/runs",
        json={
            "source_id": uploaded.json()["id"],
            "initial_rows": 100,
            "batch_rows": 700,
            "interval": 0,
        },
    )
    assert created.status_code == 201
    rid = created.json()["id"]
    service.replay(factory, settings, *service.claim(factory, "replay"))
    path = f"/api/v1/runs/{rid}/trace"
    initial = client.get(path, params={"channel_id": "c001", "batch_window": 3}).json()
    assert (initial["start_batch"], initial["end_batch"], initial["latest_batch"]) == (0, 0, 0)
    assert (initial["row_start"], initial["row_end"], len(initial["points"])) == (1, 100, 100)
    assert initial["points"][0]["forecast"] is None
    assert initial["points"][-1]["forecast"] is not None

    assert client.post(f"/api/v1/runs/{rid}/control", json={"action": "resume"}).status_code == 200
    while job := service.claim(factory, "replay"):
        service.replay(factory, settings, *job)
    assert client.get(f"/api/v1/runs/{rid}").json()["status"] == "completed"

    current = client.get(path, params={"channel_id": "c001", "batch_window": 3}).json()
    assert (current["start_batch"], current["end_batch"], current["latest_batch"]) == (2, 4, 4)
    assert (current["row_start"], current["row_end"], len(current["points"])) == (801, 2707, 1907)
    assert [point["row"] for point in current["points"]] == list(range(801, 2708))

    previous = client.get(
        path, params={"channel_id": "c001", "batch_window": 3, "end_batch": 3}
    ).json()
    assert (previous["row_start"], previous["row_end"], len(previous["points"])) == (
        101,
        2200,
        2100,
    )
    visible = {point["row"]: point for point in current["points"]}
    for point in previous["points"]:
        if point["row"] in visible:
            other = visible[point["row"]]
            assert point["value"] == other["value"]
            assert point["forecast"] == pytest.approx(other["forecast"])

    historical_initial = client.get(
        path, params={"channel_id": "c001", "batch_window": 3, "end_batch": 0}
    ).json()
    assert historical_initial["points"] == initial["points"]
    assert historical_initial["latest_batch"] == 4
    assert len(client.get(path, params={"channel_id": "c001"}).json()["points"]) == 1000

    final_batch = client.get(path, params={"channel_id": "c001", "batch_window": 1}).json()
    assert final_batch["flagged"]
    assert all(
        final_batch["row_start"] <= trigger["row_start"] <= trigger["row_end"] <= final_batch["row_end"]
        for trigger in final_batch["flagged"]
    )
