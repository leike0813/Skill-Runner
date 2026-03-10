## ADDED Requirements

### Requirement: management auth import spec MUST use ask_user upload_files payload
管理端导入规格接口 MUST 返回统一 `ask_user` 形状，不再返回旧 `required_files/optional_files` 双列表。

#### Scenario: import spec response shape
- **WHEN** 客户端调用 `GET /v1/management/engines/{engine}/auth/import/spec`
- **THEN** response MUST include `ask_user.kind=upload_files`
- **AND** `ask_user.files[]` MUST include `name` and optional `required/hint/accept`

### Requirement: management UI MUST render import dialog from ask_user.files
管理 UI MUST 基于后端 `ask_user` 提示渲染文件选择对话框。

#### Scenario: google high-risk notice
- **WHEN** `ask_user.ui_hints.risk_notice_required=true`
- **THEN** UI MUST show high-risk warning in import dialog
