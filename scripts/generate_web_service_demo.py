"""Reproducible synthetic web-service telemetry; scenario knowledge stays offline."""

import argparse
import csv
import random
from pathlib import Path

HEADERS = ("requests_per_second", "cpu_percent", "p95_latency_ms", "error_rate_percent")
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1] / "tests/fixtures/demo_web_service.csv"
)


def ramp(row: int, start: int) -> float:
    return min(1, max(0, (row - start + 1) / 300))


def write_demo(path: Path) -> None:
    rng = random.Random(2026)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(HEADERS)
        for row in range(1, 1501):
            values = (
                1000 + rng.gauss(0, 20),
                35 + rng.gauss(0, 1) + 45 * ramp(row, 701),
                120 + rng.gauss(0, 4) + 500 * ramp(row, 801),
                0.2 + rng.gauss(0, 0.03) + 3 * ramp(row, 901),
            )
            writer.writerow(f"{value:.5f}" for value in values)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    write_demo(args.output)
    print(args.output)
