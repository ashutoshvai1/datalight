"""Record-aligned CSV reading. Raw records exist only in bounded in-memory windows."""

import csv
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

EXCLUDED = {"faultnumber", "fault_status", "source", "simulationrun"}
MAX_RECORD_BYTES = 1024 * 1024
MAX_WINDOW_BYTES = 16 * 1024 * 1024
csv.field_size_limit(MAX_RECORD_BYTES)


class SourceError(ValueError):
    pass


def identity(path: Path) -> dict:
    try:
        stat = path.stat()
        if not path.is_file():
            raise SourceError("The mounted source must be a regular CSV file.")
        with path.open("rb") as f:
            digest = hashlib.sha256(f.read(65536))
            f.seek(max(0, stat.st_size - 65536))
            digest.update(f.read(65536))
        return {
            "size_bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "inode": stat.st_ino,
            "edge_sha256": digest.hexdigest(),
        }
    except OSError as exc:
        raise SourceError(
            "Mounted CSV is missing or unreadable. Check CSV_PATH and file permissions."
        ) from exc


def fingerprint(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class RecordLines:
    def __init__(self, handle: BinaryIO):
        self.handle = handle
        self.used = 0

    def __iter__(self):
        return self

    def __next__(self):
        data = self.handle.readline(MAX_RECORD_BYTES + 1)
        if not data:
            raise StopIteration
        self.used += len(data)
        if self.used > MAX_RECORD_BYTES:
            raise SourceError("CSV record exceeds the 1 MiB safety limit.")
        return data.decode("utf-8-sig")


def record(handle: BinaryIO) -> list[str] | None:
    try:
        return next(csv.reader(RecordLines(handle), strict=True), None)
    except (csv.Error, UnicodeDecodeError) as exc:
        raise SourceError("CSV must be valid UTF-8 with well-formed quoting.") from exc


def header(handle: BinaryIO) -> list[str]:
    names = record(handle)
    if not names or any(not x.strip() for x in names):
        raise SourceError("CSV requires a nonempty header with named columns.")
    normalized = [x.strip().casefold() for x in names]
    if len(set(normalized)) != len(names) or len(names) > 256:
        raise SourceError("CSV requires unique column names and at most 256 columns.")
    return names


def finite(value: str) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except ValueError:
        return None


@dataclass
class Window:
    header: list[str]
    rows: list[list[str]]
    segments: list[int]
    cursor: int
    sequence: int
    last_sample: float | None
    eof: bool
    schema_errors: int = 0
    gaps: int = 0
    duplicates: int = 0
    reversed_samples: int = 0
    invalid_samples: int = 0
    sample_index: int | None = None
    # Numeric arrays/metadata never mix: evaluation values are removed at read time.
    excluded_columns: list[str] = field(default_factory=list)


def read_window(
    path: Path,
    cursor: int,
    limit: int,
    previous_sample: float | None = None,
    sequence: int = 0,
    split_sequences: bool = True,
) -> Window:
    with path.open("rb") as f:
        names = header(f)
        kept = [i for i, n in enumerate(names) if n.strip().casefold() not in EXCLUDED]
        safe_names = [names[i] for i in kept]
        sample_index = next(
            (i for i, n in enumerate(safe_names) if n.strip().casefold() == "sample"), None
        )
        if cursor:
            f.seek(cursor)
        window_start = f.tell()
        result = Window(
            safe_names,
            [],
            [],
            f.tell(),
            sequence,
            previous_sample,
            False,
            sample_index=sample_index,
            excluded_columns=[n for n in names if n.strip().casefold() in EXCLUDED],
        )
        while len(result.rows) < limit:
            start = f.tell()
            row = record(f)
            if row is None:
                result.eof = True
                break
            if result.rows and f.tell() - window_start > MAX_WINDOW_BYTES:
                f.seek(start)
                break
            bad_schema = len(row) != len(names)
            row = (row + [""] * len(names))[: len(names)]
            row = [row[i] for i in kept]
            sample = finite(row[sample_index]) if sample_index is not None else None
            previous = result.last_sample
            resets = sample == 1 and previous is not None and previous > 1
            if resets and result.rows and split_sequences:
                f.seek(start)
                break
            if resets:
                result.sequence += 1
                previous = None
            if sample_index is not None:
                if sample is None or sample < 1 or not sample.is_integer():
                    result.invalid_samples += 1
                elif previous is not None:
                    if sample == previous:
                        result.duplicates += 1
                    elif sample < previous:
                        result.reversed_samples += 1
                    elif sample > previous + 1:
                        result.gaps += 1
            result.schema_errors += int(bad_schema)
            result.rows.append(row)
            result.segments.append(result.sequence)
            result.last_sample = sample
        result.cursor = f.tell()
        # Probe without consuming a record; handles exact-sized final batches.
        if not f.read(1):
            result.eof = True
        return result
