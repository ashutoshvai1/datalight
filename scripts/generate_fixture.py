"""Deterministic synthetic observations. Never copies the supplied industrial data."""

import csv
import math
from pathlib import Path


def write_fixture(path: Path, rows: int = 1600):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "sample",
                "signal_a",
                "signal_b",
                "held_signal",
                "flat_signal",
                "faultNumber",
                "simulationRun",
                "source",
                "fault_status",
            ]
        )
        for i in range(rows):
            local = i % 800
            base = math.sin(local * 0.17)
            shift = 14 if i >= 1000 else 0
            a = round(20 + base + shift, 5)
            b = "" if 1200 <= i < 1230 else round(40 + 2 * base, 5)
            writer.writerow(
                [
                    local + 1,
                    a,
                    b,
                    round(10 + math.sin((local // 5) * 0.23), 5),
                    7,
                    99 if i >= 1000 else 0,
                    1 + i // 800,
                    "synthetic",
                    "evaluation-only",
                ]
            )


if __name__ == "__main__":
    destination = Path(__file__).resolve().parents[1] / "tests/fixtures/demo.csv"
    write_fixture(destination)
    print(destination)
