"""Bounded-memory analysis smoke test against any mounted/local CSV. No database or model."""

import argparse
import json
import resource
import sys
import time
from pathlib import Path

from datalight import analysis
from datalight.ingestion import read_window

parser = argparse.ArgumentParser()
parser.add_argument("path", type=Path)
parser.add_argument("--batches", type=int, default=200)
args = parser.parse_args()
started = time.monotonic()
initial = read_window(args.path, 0, 500, split_sequences=False)
_, channels = analysis.classify(initial)
baseline, vectors = analysis.profiles(initial, channels, "smoke:reference")
analysis.correlations(vectors, "smoke:reference")
cursor, sample, sequence = initial.cursor, initial.last_sample, initial.sequence
rows = len(initial.rows)
for _ in range(args.batches):
    window = read_window(args.path, cursor, 100, sample, sequence)
    current, _ = analysis.profiles(window, channels, "smoke:batch")
    analysis.quality(window, current, "smoke:batch")
    analysis.detect(current, baseline, 6)
    rows += len(window.rows)
    cursor, sample, sequence = window.cursor, window.last_sample, window.sequence
    if window.eof:
        break
rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
    1024 * 1024 if sys.platform == "darwin" else 1024
)
print(
    json.dumps(
        {
            "source_bytes": args.path.stat().st_size,
            "rows_analyzed": rows,
            "channels": len(channels),
            "peak_rss_mib": round(rss, 1),
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "full_file_scan": window.eof,
        },
        indent=2,
    )
)
assert rss < 512, "Bounded-window smoke test exceeded 512 MiB peak RSS"
