"""Local source selection. Never resolve outside the configured read-only data root."""

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
    if not path.is_relative_to(root(settings)) or path.suffix.lower() != ".csv":
        raise SourceError("Select a CSV inside the configured data directory.")
    identity(path)
    return path


def choices(settings):
    base = root(settings)
    # Discovery is bounded and never opens datasets; custom paths are also supported.
    paths = sorted(p for p in base.glob("*.csv") if p.resolve().is_relative_to(base))[:100]
    return [{"path": str(p.relative_to(base)), "name": p.stem.replace("_", " ")} for p in paths]


def preview(settings, value):
    path = resolve(settings, value)
    window = read_window(path, 0, 100)
    _, channels = analysis.classify(window)
    return {
        "path": str(path.relative_to(root(settings))),
        "channels": [name for _, name in channels],
    }
