# Development context

Read hierarchically: [current state](current.md) → [durable decisions](decisions.md) → the linked active [foundation workstream](workstreams/foundation.md). Follow its links into stable documentation or code only as needed.

| File | Purpose | Owner |
|---|---|---|
| `current.md` | One compact live coordination page; replace stale state | Integration owner |
| `decisions.md` | Durable cross-workstream decisions and rationale | Integration owner with contributors |
| `workstreams/<name>.md` | Focused task context, contracts, evidence, handoff | Named workstream owner |

Keep `current.md` within about 100 lines, using the headings Objective, Constraints, Active work, Blockers, Validation, Next steps. Workstream pages use Objective, Ownership, Interfaces, Evidence, Next steps. Add pages only for active work that benefits from focused context; no future stubs.

Write enough for another person or agent to resume accurately. Record what changed the decision or continuation, not command transcripts or raw logs. Link validation commands and relevant code rather than copying outputs. Git supplies chronology. Stable operating knowledge goes in [docs](../docs/development.md); the app's evidence and review history stay in PostgreSQL.
