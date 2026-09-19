import importlib.util
from pathlib import Path

import pytest

from datalight.config import Settings
from datalight.db import Base, connect

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "fixture_generator", ROOT / "scripts/generate_fixture.py"
)
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


@pytest.fixture
def dataset(tmp_path):
    path = tmp_path / "synthetic.csv"
    generator.write_fixture(path)
    return path


@pytest.fixture
def store(tmp_path, dataset):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/app.db",
        data_path=dataset,
        data_dir=dataset.parent,
        batch_interval=0,
        llm_enabled=False,
        _env_file=None,
    )
    engine, factory = connect(settings.database_url)
    Base.metadata.create_all(engine)
    yield settings, factory
    engine.dispose()


@pytest.fixture
def started(store):
    from datalight import service
    from datalight.schemas import RunConfig
    settings, factory = store
    with factory.begin() as session:
        source = service.register_source(session, settings)
        run = service.create_run(session, source, RunConfig(interval=0))
        run_id = run.id
    return settings, factory, run_id
