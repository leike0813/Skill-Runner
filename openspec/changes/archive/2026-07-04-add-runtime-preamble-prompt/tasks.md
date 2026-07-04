## 1. OpenSpec Artifacts

- [x] 1.1 Add proposal, design, tasks, and delta specs.

## 2. Runtime Option And Secrets

- [x] 2.1 Add `preamble_prompt` to runtime option policy and validation.
- [x] 2.2 Add helper/service for normalization, redaction, secret storage, and hash extraction.
- [x] 2.3 Sanitize create/upload request runtime options so DB and audit snapshots only contain descriptors.

## 3. Cache And Prompt Injection

- [x] 3.1 Add `preamble_prompt_hash` to cache key computation and all request/upload cache-key call sites.
- [x] 3.2 Inject raw preamble only into the first initial attempt's common prompt rendering.
- [x] 3.3 Keep repair/reply/auth/recovery resume prompt paths free of repeated preamble injection.

## 4. Validation

- [x] 4.1 Add/update focused unit tests for options policy, preamble helper, cache key, request persistence, and prompt injection.
- [x] 4.2 Run OpenSpec validation.
- [x] 4.3 Run targeted pytest for affected runtime/cache/prompt paths.

## 5. Documentation

- [x] 5.1 Align user-facing runtime option, cache, prompt organization, and audit artifact documentation.
