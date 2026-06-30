## 1. OpenSpec

- [x] 1.1 Add proposal, design, task list, and delta specs for `complete-kilo-rasp-fcmp-model`.
- [x] 1.2 Validate the change with `openspec validate complete-kilo-rasp-fcmp-model --strict`.

## 2. OpenCode-family Parser Core

- [x] 2.1 Extract shared OpenCode-family runtime stream parsing and live process-event emission into common adapter code.
- [x] 2.2 Make OpenCode use the shared core without changing legacy final-output parse behavior.
- [x] 2.3 Make Kilo use the shared core while preserving Kilo-specific `type=error` handling and legacy parse behavior.

## 3. RASP/FCMP Completion Semantics

- [x] 3.1 Enable Kilo process event extraction in the runtime parser capability contract.
- [x] 3.2 Add protocol-level fallback `agent.turn_failed` evidence for failed/canceled/interrupted attempts without parser failure markers.

## 4. Tests

- [x] 4.1 Add/update Kilo parser tests for command/tool process events, live process emissions, and reasoning-token usage metadata.
- [x] 4.2 Add/update protocol tests for Kilo process-event projection and interrupted empty-output fallback.
- [x] 4.3 Run the focused pytest suite from the plan.
