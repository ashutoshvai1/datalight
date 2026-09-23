# README demo gallery

## Objective

Give repository readers a concise visual tour of Datalight using real UI screenshots of synthetic demo data.

## Ownership

Owner: current documentation agent. Scope: README, docs/screenshots, the existing cover in docs/assets, and this workstream. Preserve unrelated changes in devlog/current.md. No application or detector changes.

## Acceptance criteria

Three readable screenshots covering understanding, monitoring and evidence-backed review; repository-relative image links and descriptive captions; no real observations or credentials; inspect every image and verify documentation links.

## Evidence

Completed on 2026-09-20:

- Captured three PNGs from the running app using only `tests/fixtures/demo_web_service.csv`: 500 initial samples, 100 per batch, one-second playback interval. A new synthetic analysis was created; prior analyses were preserved.
- `docs/screenshots/monitoring.png` shows the completed replay's latest decision and the historical latency window at samples 701–1000. `understanding.png` shows the selected latency profile. `evidence-review.png` shows the final batch's question and actual configured-provider answer with eight citations. These are live UI captures, not mocked or retouched images.
- All three images were visually inspected for readable text, complete panels, and synthetic-only content. Combined size is approximately 400 KiB. README links open full-size images.
- `python3 scripts/check_devlog.py` and `git diff --check` pass. No application code changed; the full application suite was not rerun.
- No new durable operational learnings. Existing browser skill instructions cover the capture workflow.

## Refresh

Repeat the [second-domain walkthrough](../../docs/SECOND_DOMAIN_DEMO.md) with the committed synthetic CSV. Use a 1440-pixel viewport; capture the latency profile at 850 pixels high and monitoring at 1090 pixels high. Move Monitoring history to batch 5 for the drift window. Ask the latest decision what changed and what to investigate, then capture that decision card with its discussion expanded. Inspect new captures before replacing the README images.

## Branding follow-up

On 2026-09-23, the approved submission artwork replaced the README title and repeated tagline as a centered, uncropped 720-pixel-wide cover. The existing 249,054-byte JPEG keeps the asset small. Descriptive alt text preserves the project name and tagline. Quickstart, demo screenshots and privacy links follow the introduction; the screenshot gallery remains unchanged. Documentation links, the HTML image source and section anchors were checked; no application code changed.
