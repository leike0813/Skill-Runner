## 1. Claude Result Semantics

- [x] 1.1 Make Claude `type=result` completion-only by default in batch runtime parsing.
- [x] 1.2 Make Claude `type=result` completion-only by default in live NDJSON parsing.
- [x] 1.3 Keep a narrow fallback assistant-message path and mark it with `details.source = "claude_result_fallback"`.

## 2. Chat / FCMP Governance

- [x] 2.1 Preserve chat replay as an FCMP-derived view instead of patching chat directly.
- [x] 2.2 Add a regression test proving chat publication occurs after FCMP commit and consumes the committed FCMP row.
- [x] 2.3 Keep promoted/final correctness anchored to real message candidates rather than Claude result echoes.

## 3. Validation

- [x] 3.1 Add parser regressions for normal result echo, fallback-only result, and structured-output-only result cases.
- [x] 3.2 Add live emitter regressions for duplicate-final prevention and Claude fallback tagging.
- [x] 3.3 Run targeted pytest and `mypy` on the touched Claude parser / runtime publish modules.
