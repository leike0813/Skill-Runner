## 1. OpenSpec and Docs
- [x] 1.1 Create OpenSpec change artifacts for schema refresh and Gemini deprecation.
- [x] 1.2 Update README/API docs to describe active engines and Gemini legacy status.

## 2. Active Engine Schema Refresh
- [x] 2.1 Refresh Codex config schema from official Codex config docs.
- [x] 2.2 Refresh Claude settings schema from official referenced schema/docs.
- [x] 2.3 Refresh OpenCode config schema from official schema/docs.
- [x] 2.4 Refresh Qwen config schema from official settings/modelProviders docs.
- [x] 2.5 Validate and fix local active engine config files.

## 3. Gemini Soft Deprecation
- [x] 3.1 Move Gemini out of active engine keys and into legacy read-only keys.
- [x] 3.2 Remove Gemini from active adapter registry, engine upgrade/install, model/auth/status, and UI selector paths.
- [x] 3.3 Reject Gemini in skill package engine declarations and MCP registry scopes.
- [x] 3.4 Preserve read-only `.gemini` workspace/file browsing.

## 4. Tests and Validation
- [x] 4.1 Update unit/API tests for active engine lists and Gemini rejection.
- [x] 4.2 Add schema/config validation tests for active engine config assets.
- [x] 4.3 Run targeted pytest suites and OpenSpec validation.
