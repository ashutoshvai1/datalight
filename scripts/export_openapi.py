"""Generate the canonical API contract without connecting to storage."""

import json
from pathlib import Path

from datalight.api import app

destination = Path(__file__).resolve().parents[1] / "apps/web/openapi.json"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(app.openapi(), indent=2) + "\n")
print(destination)
