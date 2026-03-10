## 1. OpenSpec

- [x] 1.1 Add proposal/design/tasks for `gemini-json-first-parsing-and-rasp-raw-coalescing`.
- [x] 1.2 Add delta specs for `interactive-job-api`, `interactive-run-observability`, `ui-engine-management`.

## 2. Backend - Gemini Parser

- [x] 2.1 Implement batch-first JSON parse for stdout/stderr and key extraction (`session_id`, `response`).
- [x] 2.2 Emit parser `structured_payloads` for `parsed.json` and keep fallback compatibility.
- [x] 2.3 Apply Gemini raw row coalescing before RASP build input.

## 3. Backend - Runtime Protocol

- [x] 3.1 Extend RASP build pipeline to emit `parsed.json` events from parser structured payloads.
- [x] 3.2 Update runtime schema validation for `parsed.json` data shape.

## 4. Frontend & Docs

- [x] 4.1 Update Run Detail RASP summary mapping for `parsed.json`.
- [x] 4.2 Update `docs/api_reference.md` for `parsed.json` and raw multiline behavior.

## 5. Tests & Validation

- [x] 5.1 Add/adjust Gemini parser unit tests for batch JSON parsing and coalescing.
- [x] 5.2 Add protocol/schema tests for `parsed.json`.
- [x] 5.3 Run targeted pytest and `openspec validate` for this change.

## 6. Post-feedback Refinement - Complex stderr coalescing

- [x] 6.1 Extend raw coalescer to detect embedded JSON/array structure starts from mid-line (not only line-head).
- [x] 6.2 Add balanced bracket/brace closure scanning so prefixed structured blocks can be merged as atomic blocks.
- [x] 6.3 Reduce stack-trace fragmentation by merging contiguous lines under error-context windows.
- [x] 6.4 Add coalescer unit tests for prefixed JSON blocks, bracket-in-string safety, and stack-trace block merging.
