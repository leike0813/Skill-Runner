## 1. OpenSpec

- [x] 1.1 Add proposal/design/tasks for `ui-assistant-thinking-bubble-from-process-protocol-events`.
- [x] 1.2 Add delta specs for `interactive-job-api`, `canonical-chat-replay`, `builtin-e2e-example-client`, `ui-engine-management`.

## 2. Backend Semantics

- [x] 2.1 Extend chat replay kind set with `assistant_process`.
- [x] 2.2 Map FCMP process events (`assistant.reasoning/tool_call/command_execution`) to chat replay `assistant_process`.
- [x] 2.3 Keep `assistant.message.promoted` as boundary-only (no chat body row).
- [x] 2.4 Preserve existing `assistant_final` behavior and compatibility.

## 3. Frontend Runtime

- [x] 3.1 Add shared thinking-bubble state machine (no DOM/CSS output).
- [x] 3.2 Integrate E2E adapter with existing chat styles and lightweight process content.
- [x] 3.3 Integrate management UI adapter with existing chat styles and richer process metadata.
- [x] 3.4 Implement final dedupe: message_id first, else same-attempt normalized text exact match.

## 4. Docs & Contracts

- [x] 4.1 Update `docs/api_reference.md` with `assistant_process` chat kind semantics.
- [x] 4.2 Update chat replay invariant contract kinds/derivation rules.

## 5. Tests

- [x] 5.1 Add/adjust chat replay derivation tests for process event mapping.
- [x] 5.2 Add/adjust schema/invariant tests for `assistant_process` kind.
- [x] 5.3 Add E2E + management template semantics tests for thinking bubble rendering hooks.
- [x] 5.4 Run runtime/chat/UI regression tests for no behavior rollback.
