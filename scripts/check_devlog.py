"""Check compact context structure and repository-local Markdown links."""

import re
from pathlib import Path
from urllib.parse import unquote

root = Path(__file__).resolve().parents[1]
errors = []
required = {
    "devlog/current.md": [
        "Objective",
        "Constraints",
        "Active work",
        "Blockers",
        "Validation",
        "Next steps",
    ],
    "devlog/workstreams/foundation.md": [
        "Objective",
        "Ownership",
        "Interfaces",
        "Evidence",
        "Next steps",
    ],
}
for name, sections in required.items():
    path = root / name
    if not path.is_file():
        errors.append(f"Missing {name}")
        continue
    text = path.read_text()
    for section in sections:
        if f"## {section}\n" not in text:
            errors.append(f"{name}: missing heading {section}")
    if name.endswith("current.md") and len(text.splitlines()) > 110:
        errors.append("current.md exceeds 110 lines; replace stale context")
files = [
    root / "README.md",
    root / "AGENTS.md",
    *root.glob("docs/**/*.md"),
    *root.glob("devlog/**/*.md"),
]
for path in files:
    for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text()):
        if "://" in link or link.startswith(("#", "mailto:")):
            continue
        target = (path.parent / unquote(link.split("#")[0])).resolve()
        if not target.is_relative_to(root) or not target.exists():
            errors.append(f"{path.relative_to(root)}: broken/outside link {link}")
if errors:
    raise SystemExit("\n".join(errors))
print(f"Devlog structure and local links verified across {len(files)} documents.")
