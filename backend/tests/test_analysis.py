import csv

import pytest

from datalight import analysis
from datalight.ingestion import SourceError, read_window


def profile(path, rows=500):
    window = read_window(path, 0, rows, split_sequences=False)
    columns, channels = analysis.classify(window)
    values, vectors = analysis.profiles(window, channels, "test")
    return window, columns, values, vectors


def test_labels_never_enter_numeric_analysis(dataset, tmp_path):
    baseline = profile(dataset)
    changed = tmp_path / "relabeled.csv"
    with dataset.open() as source, changed.open("w", newline="") as output:
        rows = csv.reader(source)
        writer = csv.writer(output)
        writer.writerow(next(rows))
        for row in rows:
            row[-4:] = ["777", "888", "SECRET_EVALUATION_LABEL", "faulty"]
            writer.writerow(row)
    relabeled = profile(changed)
    assert [p.model_dump() for p in baseline[2]] == [p.model_dump() for p in relabeled[2]]
    assert baseline[0].rows == relabeled[0].rows
    assert all(
        name not in baseline[0].header
        for name in ["faultNumber", "simulationRun", "source", "fault_status"]
    )


def test_quality_and_deviation_separated_and_unusable_suppressed(dataset):
    initial, _, reference, _ = profile(dataset)
    current = read_window(dataset, initial.cursor, 500, initial.last_sample, split_sequences=False)
    shifted = read_window(dataset, current.cursor, 100, current.last_sample, current.sequence)
    channels = [(p.id, p.name) for p in reference]
    values, _ = analysis.profiles(shifted, channels, "shift")
    checks, trust = analysis.quality(shifted, values, "shift")
    deviations, unsupported = analysis.detect(values, reference, 6)
    assert trust == "trusted"
    assert not any(c.status == "fail" for c in checks)
    assert [d["channel_id"] for d in deviations] == ["c001"]
    assert any(c["channel_id"] == "c004" and "MAD" in c["reason"] for c in unsupported)
    read = read_window(dataset, shifted.cursor, 100, shifted.last_sample, shifted.sequence)
    broken = read_window(dataset, read.cursor, 100, read.last_sample, read.sequence)
    values, _ = analysis.profiles(broken, channels, "broken")
    checks, trust = analysis.quality(broken, values, "broken")
    assert trust == "partial"
    assert next(c for c in checks if c.name == "completeness").affected == 30
    deviations, unsupported = analysis.detect(values, reference, 6)
    assert any(c["channel_id"] == "c002" for c in unsupported)
    assert not any(d["channel_id"] == "c002" for d in deviations)


def test_sample_hold_and_resets_do_not_create_false_quality_flags(dataset):
    initial, _, values, _ = profile(dataset)
    assert values[2].hold_median == 5
    checks, _ = analysis.quality(initial, values, "test")
    assert next(c for c in checks if c.name == "stuck_sensor").status == "unavailable"
    rest = read_window(dataset, initial.cursor, 500, initial.last_sample, initial.sequence)
    assert len(rest.rows) == 300
    following = read_window(dataset, rest.cursor, 100, rest.last_sample, rest.sequence)
    assert following.sequence == 1
    assert not following.gaps and not following.reversed_samples
    current, _ = analysis.profiles(following, [(p.id, p.name) for p in values], "newseq")
    deviations, _ = analysis.detect(current, values, 6)
    assert deviations == []


def test_multiline_csv_checkpoint_and_parse_errors(tmp_path):
    path = tmp_path / "quoted.csv"
    path.write_text('sample,value,note\n1,4,"two\nlines"\n2,5,ok\n3,nan,ok\n4,6\n')
    first = read_window(path, 0, 1)
    assert first.rows == [["1", "4", "two\nlines"]]
    rest = read_window(path, first.cursor, 10, first.last_sample)
    assert len(rest.rows) == 3 and rest.eof and rest.schema_errors == 1
    path.write_text("a,a\n1,2\n")
    with pytest.raises(SourceError, match="unique"):
        read_window(path, 0, 10)
    path.write_text('a,b\n1,"unterminated\n')
    with pytest.raises(SourceError, match="quoting"):
        read_window(path, 0, 10)


def test_gaps_duplicates_backward_and_missing_sequence(tmp_path):
    path = tmp_path / "gaps.csv"
    path.write_text("sample,value\n1,1\n3,2\n3,3\n2,4\n1,5\n")
    w = read_window(path, 0, 20, split_sequences=False)
    assert (w.gaps, w.duplicates, w.reversed_samples, w.sequence) == (1, 1, 1, 1)
    path.write_text("value\n1\n2\n")
    w, _, values, _ = profile(path)
    checks, trust = analysis.quality(w, values, "x")
    assert trust == "untrusted"
    assert all(c.status == "unavailable" for c in checks if c.name.startswith("sequence_"))
