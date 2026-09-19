"""Select three measured TE demonstrations offline; never expose labels to live analysis."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

from datalight import analysis, temporal
from datalight.ingestion import Window


def window(header, rows):
    excluded = {"faultNumber", "simulationRun", "source", "fault_status"}
    kept = [i for i, name in enumerate(header) if name not in excluded]
    names = [header[i] for i in kept]
    sample_index = names.index("sample")
    safe_rows = [[row[i] for i in kept] for row in rows]
    segments, segment, previous = [], 0, None
    for row in safe_rows:
        sample = int(row[sample_index])
        if sample == 1 and previous is not None:
            segment += 1
        segments.append(segment)
        previous = sample
    return Window(
        names,
        safe_rows,
        segments,
        0,
        segment,
        previous,
        True,
        sample_index=sample_index,
    )


def prepare(source: Path, directory: Path, manifest: Path):
    # Only selected complete runs are retained; the multi-GB source is streamed once.
    selections = {(0, 1): [], (0, 2): [], **{(fault, 1): [] for fault in range(1, 21)}}
    provenance = {}
    with source.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        indices = {
            name: header.index(name)
            for name in ("source", "faultNumber", "simulationRun", "sample")
        }
        for position, row in enumerate(reader, 1):
            if row[indices["source"]] != "test":
                continue
            key = (
                int(float(row[indices["faultNumber"]])),
                int(float(row[indices["simulationRun"]])),
            )
            if key not in selections:
                continue
            rows = selections[key]
            if len(row) != len(header) or int(row[indices["sample"]]) != len(rows) + 1:
                raise ValueError(
                    "Selected run is malformed, duplicated or non-contiguous."
                )
            rows.append(row)
            provenance.setdefault(key, {"source_row_start": position})[
                "source_row_end"
            ] = position
            if all(len(rows) == 960 for rows in selections.values()):
                break
    if any(len(rows) != 960 for rows in selections.values()):
        raise ValueError("Expected complete 960-sample test runs.")
    healthy = selections[(0, 1)] + selections[(0, 2)]
    initial = window(header, healthy[:500])
    _, channels = analysis.classify(initial)
    models = temporal.baseline(initial, channels, {})
    initial_state = temporal.evaluate(
        initial, channels, {}, models, "offline", initial=True
    )[2]
    results = {}
    for fault in range(1, 21):
        combined = window(header, healthy + selections[(fault, 1)])
        triggers, checks, _, _, _ = temporal.evaluate(
            combined,
            channels,
            {},
            models,
            "offline",
            start_row=501,
            skip=500,
            state=initial_state,
        )
        faulty = [t for t in triggers if t.row_end > 1920]
        normal = [t for t in triggers if t.row_start <= 1920]
        results[fault] = {
            "abrupt_score": max(
                (t.score for t in faulty if t.kind == "abrupt"), default=0
            ),
            "drift_score": max(
                (t.score for t in faulty if t.kind == "drift"), default=0
            ),
            "affected_channels": len({t.channel_id for t in faulty}),
            "first_flag_row": min(
                (max(t.row_start, 1921) for t in faulty), default=None
            ),
            "first_detection_row": min((t.detected_at for t in faulty), default=None),
            "healthy_warning_intervals": len(normal),
            "quality_warning_count": sum(c.status == "fail" for c in checks),
            "intervals": [t.model_dump() for t in triggers],
        }
    selected = []
    for category, metric in [
        ("abrupt", "abrupt_score"),
        ("drift", "drift_score"),
        ("multichannel", "affected_channels"),
    ]:
        fault = max(
            (f for f in results if f not in selected),
            key=lambda f: (results[f][metric], -f),
        )
        selected.append(fault)
    directory.mkdir(parents=True, exist_ok=True)
    outputs = []
    for category, fault in zip(
        ("abrupt", "drift", "multichannel"), selected, strict=True
    ):
        output = directory / f"demo_{category}.csv"
        if output.resolve() == source.resolve():
            raise ValueError("Output cannot replace source.")
        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(healthy + selections[(fault, 1)])
        outputs.append(
            {
                "path": str(output),
                "category": category,
                "fault": fault,
                "rows": 2880,
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "runs": [
                    {"fault": f, "run": r, **provenance[(f, r)]}
                    for f, r in ((0, 1), (0, 2), (fault, 1))
                ],
                "evaluation": results[fault],
            }
        )
    details = {
        "source": str(source),
        "source_bytes": source.stat().st_size,
        "selection_is_offline_only": True,
        "outputs": outputs,
        "candidates": results,
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(details, indent=2) + "\n")
    return details


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, nargs="?", default=Path("te_process.csv"))
    parser.add_argument("--directory", type=Path, default=Path("runtime/demos"))
    parser.add_argument(
        "--manifest", type=Path, default=Path("runtime/demo-selection.json")
    )
    args = parser.parse_args()
    result = prepare(args.source, args.directory, args.manifest)
    print(
        json.dumps(
            [
                {k: v for k, v in item.items() if k != "evaluation"}
                for item in result["outputs"]
            ],
            indent=2,
        )
    )
