## 1. Change Artifacts

- [x] 1.1 Draft proposal/design/tasks for `canonical-chat-replay-ssot`.
- [x] 1.2 Add delta specs for `interactive-job-api`, `job-orchestrator-modularization`, and `canonical-chat-replay`.

## 2. Runtime Chat Replay

- [x] 2.1 Add chat replay schema, models, live journal, publisher, and audit mirror.
- [x] 2.2 Publish canonical chat replay rows from reply/auth submit/assistant final/system notice paths.
- [x] 2.3 Add `/chat` and `/chat/history` read paths with memory-first replay and audit fallback.

## 3. Frontend Adoption

- [x] 3.1 Switch user UI and management UI chat windows to `/chat` and `/chat/history`.
- [x] 3.2 Remove local optimistic chat bubble insertion.

## 4. Regression Coverage

- [x] 4.1 Update route/template tests to assert chat replay semantics instead of FCMP chat rendering.
- [x] 4.2 Add chat replay schema/publisher/journal/derivation tests.
- [x] 4.3 Run targeted pytest and mypy validation for the new chat replay path.
