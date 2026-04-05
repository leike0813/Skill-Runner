## 1. Runtime Message Semantics

- [x] 1.1 Add a dedicated non-final agent message semantic in runtime observability and parser output, separate from reasoning/tool/command process events
- [x] 1.2 Update FCMP emission so non-final agent text is published as `assistant.message.intermediate` instead of being surfaced as reasoning-before-promote
- [x] 1.3 Keep `assistant.message.promoted` / `assistant.message.final` as convergence-boundary events and narrow their dedupe responsibilities around message identity

## 2. Schema And Chat Replay

- [x] 2.1 Extend runtime protocol schema to validate `agent.message.intermediate` and `assistant.message.intermediate`
- [x] 2.2 Update canonical chat replay derivation so process events map to `assistant_process` and non-final agent text maps to `assistant_message`
- [x] 2.3 Update interactive job/chat history APIs so the new intermediate message kind is exposed without changing routes or introducing frontend-side re-derivation

## 3. Frontend Display Modes

- [x] 3.1 Add default `plain` chat mode to the built-in E2E observation UI and render non-final `assistant_message` rows as normal chat content there
- [x] 3.2 Preserve traditional `bubble` mode in the built-in E2E observation UI, keeping non-final `assistant_message` rows grouped inside the process bubble with reasoning/tool/command rows
- [x] 3.3 Add the same `plain`/`bubble` mode contract and toggle to the main run observability UI, ensuring mode switching is presentation-only

## 4. Verification And Regression

- [x] 4.1 Update runtime and replay tests to cover intermediate agent message emission, promoted/final convergence, and canonical chat replay derivation
- [x] 4.2 Update E2E and management UI tests to cover default plain mode, bubble-mode grouping, and mode-switch dedupe behavior
- [x] 4.3 Run schema validation, OpenSpec validation, and the required runtime regression suite for protocol and observability changes
