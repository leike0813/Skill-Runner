## Design Summary

This change is frontend-only and keeps all management APIs and event payloads unchanged.

### Unified Event Inspector

- Reuse the existing fixed right-side drawer and backdrop from chat inspection.
- Rename the drawer and its helpers from chat-specific naming to generic event-inspector naming.
- Introduce a single `openEventInspector(payload, sourceKind, options)` entrypoint that renders:
  - source label
  - kind/type
  - seq
  - attempt
  - created-at / ts
  - correlation summary when present
  - optional `raw_ref` preview jump
  - full JSON envelope / row payload

### Protocol Streams

- FCMP / RASP / Orchestrator rows no longer expand inline.
- Clicking a row opens the shared right-side inspector with the corresponding audit row.
- The currently inspected row stays visually selected while the drawer is open.
- Raw mode remains text-only and does not participate in drawer inspection.

### Timeline

- Timeline bubbles no longer render inline detail blocks.
- Clicking a lane bubble opens the same right-side inspector with the timeline event payload.
- The currently inspected timeline bubble stays visually selected while the drawer is open.
- Timeline loading, attempt grouping, and lane layout stay unchanged.

### Chat Hover Alignment

- Add hover styling to clickable chat entries in both plain and bubble mode.
- Keep the current focus-visible styling.
- Do not change chat semantics:
  - normal messages still open the inspector
  - thinking groups still expand/collapse
  - thinking child `View event` buttons still open the inspector
