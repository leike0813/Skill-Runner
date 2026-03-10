## ADDED Requirements

### Requirement: ask_user MUST support upload_files as a first-class kind
交互提示模型 MUST 支持 `kind=upload_files`，并通过统一 `files[]` 描述文件选择需求。

#### Scenario: pending_auth import challenge carries upload_files hint
- **GIVEN** run 处于 `waiting_auth`
- **AND** challenge kind 为 `import_files`
- **WHEN** 客户端查询 pending 交互
- **THEN** `pending_auth.ask_user.kind` MUST be `upload_files`
- **AND** `pending_auth.ask_user.files` MUST describe required/optional file items

### Requirement: upload_files parse failure MUST NOT block core runtime flow
`ask_user` 仅作为 UI hint；即使 `upload_files` hint 解析失败，核心运行状态机 MUST 保持可恢复，不得因此崩溃。

#### Scenario: malformed upload_files hint
- **WHEN** 前端无法正确解析 `ask_user.files`
- **THEN** 服务端核心状态机仍保持 `waiting_auth` 可恢复
