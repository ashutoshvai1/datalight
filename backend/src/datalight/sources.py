"""Local source selection, confined to mounted demos and persistent uploads."""

from pathlib import Path

from . import analysis
from .ingestion import SourceError, identity, read_window


def root(settings):
    return (settings.data_dir or settings.data_path.parent).resolve()


def resolve(settings, value=None):
    path = Path(value) if value else settings.data_path.resolve()
    if not path.is_absolute():
        path = root(settings) / path
    path = path.resolve()
    if (
        not any(
            path.is_relative_to(base) for base in (root(settings), settings.upload_dir.resolve())
        )
        or path.suffix.lower() != ".csv"
    ):
        raise SourceError("Select a CSV inside the configured data directory.")
    identity(path)
    return path


def choices(settings):
    base = root(settings)
    # Discovery is bounded and never opens datasets; custom paths are also supported.
    paths = sorted(p for p in base.glob("*.csv") if p.resolve().is_relative_to(base))[:100]
    return [{"path": str(p.relative_to(base)), "name": p.stem.replace("_", " ")} for p in paths]


def preview(settings, value, reader_mode="legacy"):
    path = resolve(settings, value)
    window = read_window(path, 0, 100, reader_mode=reader_mode)
    _, channels = analysis.classify(window)
    return {
        "path": str(path.relative_to(root(settings)))
        if path.is_relative_to(root(settings))
        else str(path),
        "channels": [name for _, name in channels],
    }
