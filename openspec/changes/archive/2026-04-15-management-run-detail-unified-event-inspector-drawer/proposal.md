## Why

The management run-detail page now has two different event-inspection interaction models:

- canonical chat already uses a right-side inspector drawer
- FCMP / RASP / Orchestrator streams and the timeline still expand details inline

That split causes layout jumps, makes comparison harder, and forces operators to mentally switch between inspection patterns on the same screen.

## What Changes

- Generalize the existing chat inspector into a shared right-side event inspector for chat, protocol streams, and timeline events.
- Remove inline detail expansion from the FCMP / RASP / Orchestrator panes and the timeline.
- Add visible hover feedback to clickable chat entries so their inspectability matches the protocol panes.

## Capabilities

### Modified Capabilities
- `web-management-ui`

## Impact

- Affected code: `server/assets/templates/ui/run_detail.html`
- Affected tests: management UI template guards and integration coverage
