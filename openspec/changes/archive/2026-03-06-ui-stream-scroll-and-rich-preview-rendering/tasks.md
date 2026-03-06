## 1. OpenSpec Artifacts

- [x] 1.1 Create change folder and proposal/design/tasks.
- [x] 1.2 Add delta specs for management UI and interactive job API.

## 2. Stream Window Scroll Governance

- [x] 2.1 Add per-stream near-bottom detection and auto-follow state.
- [x] 2.2 Remove forced scroll-to-bottom on every refresh.
- [x] 2.3 Keep both summary mode and raw mode compatible with new scroll policy.

## 3. Protocol Bubble Enhancement

- [x] 3.1 Enrich RASP summary text with category/type/source and key fields.
- [x] 3.2 Add protocol kind tags for major event groups.
- [x] 3.3 Implement per-stream accordion drilldown with mutually exclusive expansion.
- [x] 3.4 Add detail panel with key-value summary, full JSON, and raw_ref jump action.

## 4. Rich File Preview Rendering

- [x] 4.1 Extend format detection to yaml/toml/python/javascript.
- [x] 4.2 Add syntax-highlight HTML rendering with safe fallback.
- [x] 4.3 Upgrade management preview visual contrast styles.
- [x] 4.4 Add fixed-height scroll container for Skill Browser preview.

## 5. Tests

- [x] 5.1 Add renderer unit tests for yaml/toml/python/javascript highlighting.
- [x] 5.2 Update UI template tests for protocol auto-follow and accordion details.
- [x] 5.3 Update management skill detail tests for preview scroll container.

## 6. Post-feedback Refinement

- [x] 6.1 Make preview highlighting end-to-end visible in management UI and E2E UI (not markdown-only).
- [x] 6.2 Introduce shared File Explorer module and reuse in run detail, skill browser, and E2E run observe.
- [x] 6.3 Add directory collapse to Skill Browser file tree (default collapsed).
- [x] 6.4 Normalize Run Observation layout: fixed protocol pane heights, collapsed full-width stderr with alert dot, and move Cancel Run to status card.
