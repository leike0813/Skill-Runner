## ADDED Requirements

### Requirement: Management run detail MUST use one shared event inspector drawer
The management run-detail page MUST use a single right-side event inspector drawer for chat, protocol streams, and timeline event inspection.

#### Scenario: operator inspects a protocol stream row
- **WHEN** the operator clicks a FCMP, RASP, or Orchestrator row while raw mode is disabled
- **THEN** the page MUST open the shared right-side event inspector drawer
- **AND** it MUST show the corresponding audit row envelope
- **AND** it MUST NOT expand a local inline detail block inside the protocol pane

#### Scenario: operator inspects a timeline event
- **WHEN** the operator clicks a timeline bubble
- **THEN** the page MUST open the same shared right-side event inspector drawer
- **AND** it MUST show the corresponding timeline event payload
- **AND** it MUST NOT expand a local inline detail block inside the timeline pane

### Requirement: Management run detail chat MUST expose clickable affordance
Clickable chat items in the management run-detail page MUST provide visible hover or focus feedback.

#### Scenario: operator hovers a clickable chat message
- **WHEN** the operator hovers a clickable chat entry
- **THEN** the entry MUST show a visible hover affordance aligned with the protocol-pane interaction style
- **AND** the existing keyboard focus indication MUST remain available
