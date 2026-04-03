# Design: claude-raw-suppression-and-sandbox-deployment-hardening

## Raw Suppression

Claude already emits semantic outputs (`assistant_messages`, `process_events`, `turn_markers`, `run_handle`) with `raw_ref`, but live and rebuild paths still left too many overlapping raw rows.

The fix has two parts:

1. Mark all semantic-consumed Claude rows as consumed during stream parsing.
2. Delay live raw emission until finish for Claude, then let the existing suppression chain drop overlapping rows.

This keeps the runtime protocol shape unchanged and only reduces duplicate `raw.stdout`.

## Sandbox Diagnostics

Claude sandbox remains enabled by default. This change does not introduce fail-closed behavior.

Instead it adds stable warning-level diagnostics for:

- missing `bubblewrap` / `bwrap`
- missing `socat`
- sandbox initialization/runtime failures
- commands blocked by Claude sandbox

Diagnostics appear in:

- parser diagnostics
- CLI `preflight/status/doctor`
- management UI engine status hints

## Containerization

The runtime image installs `bubblewrap` and `socat` so Claude sandbox can work inside Docker without manual package installation.
