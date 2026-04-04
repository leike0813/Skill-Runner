## MODIFIED Requirements

### Requirement: auth payload MUST expose phase and timeout metadata

Auth-related payload 在会话人工 OAuth 返回内容场景下 MUST 使用 `auth_code_or_url` 作为规范值。

#### Scenario: pending auth and auth.input.accepted use auth_code_or_url

- **WHEN** runtime schema 校验 `PendingAuth` 或 `auth.input.accepted`
- **THEN** schema MUST 接受 `auth_code_or_url`
- **AND** MUST NOT 继续要求 `authorization_code`
