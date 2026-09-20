# Demo UI

Owner: charts agent, branch `codex/demo-ui`, isolated worktree `/private/tmp/datalight-ui`.

Scope: chart lifecycle, monitoring history viewport, correlation matrix, numbered citations,
name-free review and continued questions, and the Docs page. Root owns application navigation,
monitoring setup, generated contracts and end-to-end workflow verification.

Dependencies: trace supports `batch_window=3` and optional `end_batch`, returning start/end/latest
batch indices and row bounds. Reviews default operator identity server-side. Answers include
context from the latest ten completed question/answer turns for the same decision. Custom rule
matches are optional on historical decisions.

Acceptance: latest three batches by default with browsable pinned history; expanded matrix with
pair names, missing-value explanation and static color legend; numbered evidence; follow-up
questions remain available without entering a name; source-grounded plain-language Docs.

## Handoff

Implemented expanded correlation matrix with full-pair rich-text tooltips, gray unavailable cells,
and a static labeled color legend. Explanations, answers and custom-rule matches share numbered
citations. Chart instances survive option updates. Monitoring defaults to three batches, includes
a native horizontal history scrollbar with keyboard support, pins historical browsing during
polling, and offers Latest to return to following. Excluded channels are omitted from its selector.

Reviews submit without an operator name. An always-available composer inside the discussion
supports follow-ups and disables sending while a question is pending. Review and question drafts
are separate. Custom-rule matches display their effect and evidence.

Docs explains profile/prediction/reference metrics, exact automatic thresholds, custom-rule
confirmation/locking, evidence records, privacy and ten-turn model context. Root registers the route.

Validation: TypeScript check, ESLint on owned TSX files and production Vite build passed in this
worktree. Browser and integrated API checks remain with the integration owner. Existing Vite
large-chunk warning remains. Temporary contract intersections allow checks before regenerated
trace/rule/exclusion contracts; root may simplify them after generation.

Integration: preserve root MonitoringSetup edits in Understanding and both appended CSS groups.
No generated contract files or end-to-end workflow tests were changed.
