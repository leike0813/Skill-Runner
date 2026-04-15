## ADDED Requirements

### Requirement: Management run detail chat MUST use the shared markdown renderer
The management run-detail page MUST render canonical chat with the same shared markdown renderer and scoped markdown styles used by the built-in E2E observe client.

#### Scenario: markdown chat content appears in run detail
- **WHEN** the management run-detail page renders chat text from `/chat` or `/chat/history`
- **THEN** it MUST use the shared chat markdown assets
- **AND** it MUST render formulas, code blocks, lists, tables, and quotes with the same markdown capabilities as the E2E observe page
- **AND** it MUST NOT rely on browser default paragraph margins for chat spacing

### Requirement: Management run detail MUST expose raw chat event inspection
The management run-detail page MUST allow operators to inspect the raw `chat-replay` event envelope behind chat items without leaving the canonical chat view.

#### Scenario: operator inspects a chat bubble
- **WHEN** the operator clicks a normal chat bubble
- **THEN** the page MUST open a right-side inspector drawer
- **AND** the drawer MUST show the corresponding raw `chat-replay` event envelope
- **AND** the drawer MAY expose a `raw_ref` preview jump when available

#### Scenario: operator inspects a thinking or process child item
- **WHEN** the operator expands a thinking/process group and selects a child item inspector trigger
- **THEN** the page MUST open the same inspector drawer for that child item's `chat-replay` event envelope
- **AND** the expand/collapse interaction MUST remain intact
