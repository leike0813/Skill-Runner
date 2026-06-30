## 1. OpenSpec

- [x] 1.1 Create proposal, design, delta specs, and task list for Kilo phase 2.
- [x] 1.2 Validate the change with `openspec validate complete-kilo-code-engine-phase2 --strict`.

## 2. Auth Strategy And Registry

- [x] 2.1 Change Kilo auth strategy schema/config from disabled to provider-aware.
- [x] 2.2 Add Kilo provider registry that composes Kilo Gateway with OpenCode providers.
- [x] 2.3 Register Kilo in shared provider-aware auth and driver matrix.

## 3. Kilo Gateway Auth

- [x] 3.1 Add Kilo Gateway device auth flow with start, poll, credential persistence, and redacted errors.
- [x] 3.2 Add Kilo auth runtime handler that handles Gateway locally and delegates third-party providers to OpenCode behavior.
- [x] 3.3 Wire Kilo auth flow and handler into engine auth bootstrap.

## 4. Config And Model Semantics

- [x] 4.1 Allow Kilo `provider` config while keeping user-authored `mcp` roots rejected.
- [x] 4.2 Set Kilo profile to multi-provider model semantics and preserve complete runtime model IDs.

## 5. Tests

- [x] 5.1 Update auth strategy, provider registry, driver matrix, config composer, model registry, and auth flow manager tests.
- [x] 5.2 Run OpenSpec validation and focused pytest suite.
