# Change Proposal: claude-raw-suppression-and-sandbox-deployment-hardening

## Why

Run `0fcd495a-9cb8-47d7-8cf3-803015ffde33` exposed two issues in the Claude integration:

- Claude still emits too many duplicated `raw.stdout` events even after semantic parsing succeeds.
- Claude sandbox depends on `bubblewrap` and `socat`, but container assets and diagnostics did not make that dependency explicit enough.

These issues do not justify changing Claude's default security posture, but they do require better suppression and better warning-level observability.

## What Changes

- Tighten Claude raw suppression so semantic-consumed rows stop reappearing as `raw.stdout`.
- Add warning-level Claude sandbox diagnostics for missing dependencies, sandbox initialization failures, and sandbox-blocked commands.
- Install Claude sandbox dependencies in the runtime image and document them clearly.
- Surface Claude sandbox dependency warnings through CLI diagnostics and management UI status without turning them into hard failures.

## Impact

- Less duplicated raw output for Claude runs.
- Better visibility when Claude sandbox is degraded.
- Container deployments become Claude-sandbox-ready by default.
