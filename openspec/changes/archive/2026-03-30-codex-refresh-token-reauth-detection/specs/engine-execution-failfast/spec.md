## ADDED Requirements

### Requirement: Codex refresh-token reauth exits MUST be attributable as AUTH_REQUIRED

当 Codex 因 refresh token 失效族错误而非零退出时，系统 MUST 能基于高置信度 auth signal 将该失败归因为 `AUTH_REQUIRED`，从而复用既有 `waiting_auth` 流程。

#### Scenario: codex refresh-token reauth failure can enter waiting_auth
- **GIVEN** interactive Codex run 的 parser 产出 `confidence=high` 的 `codex_refresh_token_reauth_required`
- **WHEN** 进程以非零退出结束
- **THEN** lifecycle 必须可进入 `waiting_auth`
- **AND** 使用现有 Codex method-selection / auth session 机制
