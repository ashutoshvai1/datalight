# Demo conversation

## Claim

Owner: conversation agent on `codex/demo-conversation`.
Scope: backend question history, privacy checks, anonymous local reviews, and focused tests.
Dependencies: integration owns generated contracts; frontend owns conversation presentation.
Acceptance: follow-up questions carry at most ten completed, sanitized exchanges from the same decision; retries reuse the queued snapshot; only one unanswered question can be queued per decision; old reviews remain immutable.

## Handoff

Implemented:

- Review requests default to `Local user`; old named reviews remain unchanged.
- A finding-row lock serializes question submission and returns 409 while an answer is pending.
- Question jobs snapshot the sanitized current question and up to ten successful prior exchanges from that decision. Lease recovery reuses that snapshot.
- Typed provider conversation context is explicitly non-authoritative; citation validation still requires real current decision evidence.
- All known numeric headers become opaque IDs. Unsupported/evaluation headers are rejected; sequence names become a generic ordering-coordinate label. Historical answers are sanitized before being reused. User turns retain numeric-sequence and multiline protection.
- Decision Q&A omits excluded profiles, relationships, per-channel quality summaries, and forecast errors using the forthcoming `excluded_channel_ids` configuration field defensively.

Validation: provider suite 10 passed; full CPU suite 26 passed; focused Ruff and backend mypy passed. A PostgreSQL concurrency regression was added but not run here; integration owns PostgreSQL verification, generated API contracts, and frontend workflow checks.

Integration notes: public review creation now makes `operator` optional with a default, so regenerate contracts. UI should disable follow-up submission while the last answer is pending and retain server 409 handling. Context retains ten successful pairs; full review history remains persisted. Update D006 and architecture wording about required names. The provider-only conversation schema needs no database migration.
