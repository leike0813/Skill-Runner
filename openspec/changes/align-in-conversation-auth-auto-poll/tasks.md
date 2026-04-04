## OpenSpec

- [x] Create change directory and `.openspec.yaml`
- [x] Write `proposal.md`
- [x] Write `design.md`
- [x] Add delta specs for in-conversation auth semantics, runtime schema, and E2E client behavior

## Implementation

- [x] Align conversation auth strategy values to `auth_code_or_url`
- [x] Update interactive auth enums and pending payload generation
- [x] Make waiting_auth consume strategy `session_behavior` and `in_conversation.transport`
- [x] Align E2E waiting_auth submission defaults with the new protocol
- [x] Update runtime contract and FCMP auth input fallback values

## Validation

- [x] Update targeted unit tests for strategy service, waiting_auth orchestration, and E2E template semantics
- [x] Run targeted pytest suites
- [x] Run required runtime auth/protocol regression suites
- [x] Run focused mypy checks for touched files
