## 1. OpenSpec

- [x] 1.1 Add proposal/design/tasks for `generic-process-events-and-final-promotion-contract-hardening`.
- [x] 1.2 Add delta specs for `interactive-job-api`, `interactive-run-observability`, `session-runtime-statechart-ssot`, `runtime-event-ordering-contract`.

## 2. Contracts & Types

- [x] 2.1 Extend runtime contract RASP/FCMP event enums with generic process events and `*.message.promoted`.
- [x] 2.2 Add/align payload schema fields (`message_id`, `summary`, `details`, `classification`, `text` rules).
- [x] 2.3 Update `server/models/runtime_event.py` FCMP type enum to include new assistant process event names.

## 3. Protocol Core

- [x] 3.1 Add generic `FinalPromotionCoordinator` and wire it into live publish flow.
- [x] 3.2 Publish process events immediately; publish promoted+final on turn-end signal.
- [x] 3.3 Enforce fallback promotion only for `succeeded|waiting_user`; forbid fallback for `failed|canceled`.
- [x] 3.4 Keep RASP `agent.*` / FCMP `assistant.*` naming boundary strict in mapping.

## 4. Codex Integration

- [x] 4.1 Add parser-process declaration in codex adapter profile (tool_call / command_execution / turn-end).
- [x] 4.2 Update Codex parser to emit generic process inputs and turn-end signals without core hardcoding.
- [x] 4.3 Ensure non-structured lines still preserve raw traceability.

## 5. SSOT & Docs

- [x] 5.1 Update statechart/sequence/runtime protocol docs for promoted/final convergence semantics.
- [x] 5.2 Update invariants for naming boundary, promotion ordering, and terminal fallback constraints.
- [x] 5.3 Update `docs/api_reference.md` with protocol event-type expansion semantics.
- [x] 5.4 Add artifact `artifacts/fcmp_rasp_protocol_delta_process_events_v1.md`.

## 6. Tests

- [x] 6.1 Add schema/invariant tests for new event types and payload constraints.
- [x] 6.2 Add protocol behavior tests for immediate process publish + promoted/final convergence.
- [x] 6.3 Add Codex regression tests for multi-message turn: non-last -> reasoning, last -> final.
- [x] 6.4 Verify running/terminal observability set consistency remains stable.
