## 1. Declaration Single Source

- [x] 1.1 Rename adapter profile contract field to `parser_auth_patterns.rules`.
- [x] 1.2 Update adapter profile loader to expose `parser_auth_patterns`.
- [x] 1.3 Migrate codex/gemini/iflow/opencode profiles to `parser_auth_patterns`.

## 2. Parser Signalization

- [x] 2.1 Add `auth_signal` to `RuntimeStreamParseResult`.
- [x] 2.2 Add shared parser-side matcher for declarative auth patterns.
- [x] 2.3 Implement parser-driven `auth_signal` output for all four engines.

## 3. Runtime/Lifecycle Hard Cut

- [x] 3.1 Switch adapter early-exit probe to consume parser `auth_signal` only.
- [x] 3.2 Remove runtime path dependency on rule-based `auth_detection_service.detect(...)`.
- [x] 3.3 Switch lifecycle terminal auth classification to parser signal normalization.

## 4. Regression & Guard Tests

- [x] 4.1 Update adapter profile loader/rule loader tests for `parser_auth_patterns`.
- [x] 4.2 Update auth detection fixtures/tests to pass parser-derived runtime parse result.
- [x] 4.3 Validate early-exit behavior with parser signal under idle blocking.
- [x] 4.4 Run targeted orchestrator/auth/protocol regressions.
