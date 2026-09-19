"""Restart the synthetic Compose deployment and verify durable replay/reviews."""

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from itertools import pairwise
from pathlib import Path

from datalight.ingestion import identity

base = os.environ.get("BASE_URL", "http://localhost:8080").rstrip("/")


def api(path, data=None):
    request = urllib.request.Request(
        base + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def until(check, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if result := check():
                return result
        except (urllib.error.URLError, ConnectionError):
            pass
        time.sleep(0.25)
    raise AssertionError("Local deployment did not reach the expected state in time.")


expected = identity(Path("tests/fixtures/demo.csv"))
actual = api("/api/v1/system")["source"]["identity"]
assert all(actual[key] == expected[key] for key in ("size_bytes", "edge_sha256")), (
    "Restart smoke requires the included synthetic CSV; refusing to alter another source's run."
)
run = api("/api/v1/runs", {"initial_rows": 500, "batch_rows": 100, "interval": 30})
path = f"/api/v1/runs/{run['id']}"
until(lambda: api(path)["rows_processed"] >= 500)
paused = api(path + "/control", {"action": "pause"})
finding = api(path + "/findings?category=assumption")[0]
reviews_path = f"/api/v1/findings/{finding['id']}/reviews"
for action in ("accept", "question", "override"):
    api(
        reviews_path,
        {
            "action": action,
            "operator": "Restart smoke",
            "reason": "Synthetic persistence validation.",
            "replacement": "Reference remains provisional."
            if action == "override"
            else None,
        },
    )
subprocess.run(["docker", "compose", "restart", "db", "api", "worker"], check=True)
until(lambda: api("/healthz")["status"] == "ok")
assert api(path)["rows_processed"] == paused["rows_processed"]
assert len(api(reviews_path)) == 3
assert api(path + "/findings?category=assumption")[0] == finding
api(path + "/control", {"action": "resume"})
api(path + "/control", {"action": "fast_forward"})
until(lambda: api(path)["status"] == "completed")
batches = sorted(api(path + "/batches"), key=lambda b: b["index"])
assert len(batches) == 12 and len({b["index"] for b in batches}) == 12
assert batches[0]["row_start"] == 1 and batches[-1]["row_end"] == 1600
assert all(a["row_end"] + 1 == b["row_start"] for a, b in pairwise(batches))
assert len(api(reviews_path)) == 3
print(
    "Database/API/worker restart passed: checkpoint, 3 reviews, original evidence, 12 unique contiguous batches."
)
