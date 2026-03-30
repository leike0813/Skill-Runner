## ADDED Requirements

### Requirement: Codex refresh-token reauth failures MUST produce a high-confidence auth signal

Codex runtime output 中明确表示 refresh token 已失效且需要重新登录的文案 MUST 触发 engine-specific 高置信度 `auth_signal`，不得只落入 common low-confidence fallback。

#### Scenario: refresh token reused triggers codex high-confidence auth signal
- **GIVEN** Codex 输出包含 `refresh_token_reused`
- **AND** 输出同时包含 `sign in again` 或 `log out and sign in again`
- **WHEN** parser 执行 auth detection
- **THEN** 必须产出 `auth_signal.required=true`
- **AND** `confidence=high`
- **AND** `matched_pattern_id=codex_refresh_token_reauth_required`

#### Scenario: expired token refresh path stays engine-specific
- **GIVEN** Codex 输出包含 `Provided authentication token is expired`
- **AND** 输出同时表明需要重新登录
- **WHEN** parser 执行 auth detection
- **THEN** 该样本必须命中 Codex engine-specific 规则
- **AND** 不得仅依赖 `generic_token_expired_text_fallback`
