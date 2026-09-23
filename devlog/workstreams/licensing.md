# Repository licensing

## Objective and ownership

Owner: documentation agent. Apply the user's Apache 2.0 decision to the root license, README and package metadata. Preserve unrelated local edits and artwork. No application behavior or dependency changes.

## Acceptance criteria

Use the official Apache 2.0 text unchanged; declare the same SPDX identifier in both packages; distinguish third-party materials; validate documentation links and metadata before committing and pushing.

## Validation

Verified on 2026-09-23: root LICENSE matches the official Apache download byte-for-byte, both package manifests parse and declare `Apache-2.0`, documentation link checks and `git diff --check` pass. Reviewed the licensing diff; no application behavior changed, so the application test suite was not rerun.
