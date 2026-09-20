# Architecture

The product is generic CSV understanding, quality assessment, change monitoring and review. [DATASET.md](DATASET.md) describes an offline testbed; it is never runtime model context.

## Data flow and interfaces

A read-only data directory feeds a bounded CSV reader. `GET /sources` lists choices, `/sources/preview?path=…` infers numeric channels, and `POST /runs` explicitly creates an analysis with path, initial count, batch size, interval and optional channel limits. Resolved paths, including symlinks, must stay within the configured root. Startup creates no run. `POST /sources/upload` streams a multipart CSV into a separate persistent uploads root with generated filenames and returns an opaque source ID. Preview and run creation also accept that source ID. Uploaded files use file row order; legacy mounted files preserve sample-reset ordering. Evaluation fields and sample remain excluded as features in both modes. Uploads default to a configurable 256 MiB limit; validation is bounded and later malformed records remain ordinary quality evidence.

FastAPI serves versioned `/api/v1` resources. PostgreSQL owns source identities, runs, jobs, reports, evidence, immutable batch decisions, reviews, answers and model attempts. Nginx serves React. The worker has independent replay, initial-interpretation, question and rule-proposal loops. OpenAPI generates browser contracts.

A report adds typed per-channel prediction metrics and explanations. `/runs/{id}/decisions` supplies typed decisions plus the current human assessment. `/runs/{id}/trace?channel_id=…` rereads bounded recent source records to return up to 1,000 points and forecasts for legacy callers. The UI supplies `batch_window=3` and optional `end_batch` to retrieve three actual batch windows with their boundary metadata. Older windows are reread on demand; browsing does not load the full history into browser memory. `/findings/{id}/reviews` appends reviews; `/findings/{id}/answers` returns persisted answers. Legacy findings, evidence, model-call, audit and SSE resources remain accessible outside the simplified UI.

## Temporal analysis

`analysis.py` computes profiles and correlations. `temporal.py` implements causal sample-window analysis with no dataset labels, physical channel identities, or playback-time assumptions.

- Every trailing 10-sample window fits an OLS line against positions 0–9. Each horizon 1–5 is scored only when its target arrives. MAE averages all valid forecast/target pairs; the chart shows horizon 5. Mean signed slope and slope standard deviation summarize the initial window.
- Abrupt change compares the difference between adjacent 10-sample means with the distribution of those differences in the initial window.
- Drift uses a trailing 50-sample slope, evaluated every 10 samples from each continuous sequence start. Three consecutive evaluations must exceed the reference threshold in the same direction.
- Level deviation uses a trailing 10-sample median against the initial value distribution. This retains fixed-reference deviation detection while removing dependence on playback batch size.
- Reference center is the median. Scale is `max(1.4826*MAD, standard deviation, tolerance)`; tolerance is `max(1e-12, 1e-9*max(abs(initial valid values)))`. The trigger threshold is six scales. Fewer than three valid reference metrics makes a rule unavailable.
- Invalid/out-of-range values invalidate affected temporal windows. Sample gaps, duplicates, reversal, or independent-run boundaries break windows; they are never interpolated. Counters and forecast context carry across ordinary batches.
- Equal-value holds use exact equality. A frozen warning requires at least `max(20, ceil(5*median(initial completed hold lengths)))` samples. Holds censored by sequence ends or missing values are not used to infer typical completed cadence. Constant initial channels are marked inconclusive.

Initial ranges are observational, not physical limits. Configured bounds are checked separately and excluded from temporal model inputs. Quality checks do not directly set process status. A batch is Fault Suspected if any process rule triggers; otherwise OK. OK with insufficient assessment explicitly warns about limited coverage. Coverage counts channels with usable baseline rules and at least one valid 50-sample assessment in the batch. Consecutive triggered samples are stored as intervals with their strongest metric, first detection coordinate, and affected range.

## Replay and recovery

The initial report commits in a paused state unless the source is exhausted. Play atomically locks the saved monitoring settings and schedules the first monitoring batch immediately; subsequent batches are scheduled after the configured interval. Batches stop at independent sequence resets and may be shorter than requested. The last partial batch is processed normally.

Source replacement checks use size, mtime, inode, and hashes of the first/last 64 KiB. They are not a full-file cryptographic identity check. Files are assumed static during an analysis. Source changes require a new analysis.

Jobs use `FOR UPDATE SKIP LOCKED`, token ownership, and five-minute leases. Unique `(run_id, kind, task_key)` identities support report groups and individual questions. Run locks serialize controls with replay. Evidence, decision, batch, counters, history offsets and cursor commit together. State stores counters and the location of up to 69 preceding records; raw observations remain in the CSV and are reread locally. Trace access verifies source identity too.

Database triggers prohibit updates/deletes to evidence, findings, reviews, answers, batches and audit events. A new analysis stops prior active work without deleting history. Old report fields have compatible defaults; old analyses require a new run to use the new detector version. Internal fast-forward remains for tests/backward compatibility, absent from the interface.

## Model and review boundaries

Only typed aggregate/question payloads and sanitized rule-proposal requests leave the backend. Initial requests contain at most eight target channels, their profiles/predictions/quality, and up to three strongest relationships per target. Responses must cover exactly those channels and cite their own profile and prediction evidence. Partial group failures remain explicit.

Questions are explicit user-provided text plus aggregate decision evidence and forecast errors. Each job snapshots at most ten preceding completed exchanges from the same finding; retries reuse that context. Only one question may be pending per decision. The complete local transcript remains available. Prior model answers supply conversational context, not new evidence. Original names are replaced with opaque IDs; numerical sequences and evaluation metadata are rejected. No raw CSV rows, observation arrays, original names or evaluation values are attached. Questions cannot change rules or decisions. Credentials stay in the authorization header, redirects are disabled, responses are bounded, and reflected configured keys are redacted.

Every model attempt stores its purpose, request, response/status and timestamps. Interrupted calls have an unknown outcome before retry; exactly-once external execution is not promised. Local publication remains idempotent under job leases. Evidence validation does not establish that a model explanation is correct.

One decision is appended for each monitoring batch, including OK. Accept, question and override append history. The latest accept/override determines the displayed human assessment; a question does not change it. Accept returns to the automated assessment, and override requires OK/Fault Suspected plus a reason. No action recalibrates the initial reference. New reviews default to Local user without a name input; existing named history is preserved. Authentication and multi-tenancy are not included.

## Monitoring configuration and user rules

After the initial report, `POST /runs/{id}/monitoring-config` saves excluded channel IDs and retained applied-rule IDs. At least one numeric channel is required. These settings lock at first Play, even if playback is immediately paused. The original understanding report and fixed references remain unchanged; excluded channels no longer contribute monitoring profiles, checks, coverage, forecasts or model summaries.

`POST /runs/{id}/rule-proposals` creates a leased model job from a sanitized request and eligible opaque channel IDs. A proposal supports one comparison (`gt`, `gte`, `lt`, `lte`), outside an inclusive range, or missing-value check. Blank values are missing; invalid numbers remain separate quality failures. Proposals contain no code. Unknown channels, nonfinite thresholds, ambiguous effects and unsupported compound/temporal requests cannot be applied. The proposal GET endpoint exposes status and the typed candidate; its `/apply` endpoint revalidates eligibility and the first-Play lock under the run lock.

Applied rules are versioned in run configuration. Fault-effect violations contribute to Fault Suspected; quality-effect violations only add warnings. Rules evaluate independently of temporal quality masking and never recalibrate references. Each batch records typed rule matches and immutable evidence with rule ID/version, criterion, violation count and intervals. Pending or failed proposals have no monitoring effect.
