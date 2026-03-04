## ADDED Requirements

### Requirement: auth input submit MUST record accepted event through schema-aligned orchestrator payload
系统 MUST 在 callback/code 提交被接受时写入合法的 `auth.input.accepted` orchestrator event，并继续后续 auth 处理流程。

#### Scenario: callback URL 提交成功记录 accepted event
- **GIVEN** run 处于 `waiting_auth`
- **WHEN** 客户端提交合法 callback URL
- **THEN** 系统 MUST 写入通过 schema 校验的 `auth.input.accepted`
- **AND** `auth.input.accepted.data` MUST 至少包含 `auth_session_id` 与 `submission_kind`

#### Scenario: canonical accepted timestamp is preserved
- **WHEN** 系统接受 callback URL 或 auth code 输入
- **THEN** 系统 MAY 在 `auth.input.accepted.data` 中记录 canonical `accepted_at`
- **AND** 该字段 MUST 与 runtime schema contract 对齐

#### Scenario: schema drift does not abort accepted auth input with internal error
- **GIVEN** 提交内容本身合法
- **WHEN** 系统处理 auth input submit
- **THEN** auth input 路径 MUST NOT 因 orchestrator event schema 漂移返回 `500`
- **AND** 系统 MUST 继续后续 auth processing 或返回明确的业务错误
