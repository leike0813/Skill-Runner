## Why

当前 Codex 对 refresh token 失效的错误文案只能命中 `generic_token_expired_text_fallback`，因此只会产出 low-confidence `auth_signal`。这会导致像 run `9440bc11-f476-4e3d-a01f-05a3151bdcef` 这样的真实鉴权失效，只表现为普通非零退出，而不会进入会话内 `waiting_auth` / 重新鉴权流程。

## What Changes

- 为 Codex 新增一条 engine-specific 高置信度 auth detection 规则，覆盖 refresh token 失效族文案。
- 将这类明确要求重新登录的 Codex 错误从 generic fallback 提升为 `confidence=high`。
- 补齐 auth detection fixture 与 Codex/lifecycle 回归测试，确保此类错误可进入既有会话内鉴权路径。

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `auth-detection-layer`: Codex refresh token 失效族文案必须产出高置信度 `auth_signal`
- `engine-execution-failfast`: Codex refresh token 失效导致的非零退出必须可升级为 `AUTH_REQUIRED`

## Impact

- Affected code: `server/engines/codex/adapter/adapter_profile.json`
- Affected fixtures/tests:
  - `tests/fixtures/auth_detection_samples/codex/openai_refresh_token_reused_401/`
  - `tests/unit/test_auth_detection_codex.py`
  - `tests/unit/test_auth_detection_lifecycle_integration.py`
- No public API changes; observable change is that Codex refresh-token reauth failures can now enter `waiting_auth`
