## ADDED Requirements

### Requirement: Engine 管理页 MUST 使用 transport 分组鉴权接口
系统 MUST 让 Engine 管理页调用 transport 分组接口，而非旧的通用会话接口。

#### Scenario: 发起 oauth_proxy 会话
- **WHEN** 用户点击 OAuth 代理入口
- **THEN** 前端调用 `/ui/engines/auth/oauth-proxy/sessions`

#### Scenario: 发起 cli_delegate 会话
- **WHEN** 用户点击 CLI 委托入口
- **THEN** 前端调用 `/ui/engines/auth/cli-delegate/sessions`

### Requirement: UI MUST 正确展示 transport 专属状态机语义
系统 MUST 根据 transport 展示状态，不得混用状态机含义。

#### Scenario: oauth_proxy 状态展示
- **WHEN** 当前会话 `transport=oauth_proxy`
- **THEN** 页面不得显示 `waiting_orchestrator` 语义

#### Scenario: cli_delegate 状态展示
- **WHEN** 当前会话 `transport=cli_delegate`
- **THEN** 页面可显示 `waiting_orchestrator`，表示后台自动编排阶段

### Requirement: UI MUST 消费标准化会话快照与日志根路径
系统 MUST 让 UI 基于标准化快照渲染，并可读取 `log_root` 用于诊断跳转。

#### Scenario: 拉取会话快照
- **WHEN** 页面轮询鉴权会话状态
- **THEN** 返回字段包含 `transport_state_machine`、`orchestrator`、`log_root`
- **AND** UI 不再依赖解析 transport 特有原始日志文本
