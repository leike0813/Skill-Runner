## ADDED Requirements

### Requirement: Engine 管理页 MUST 支持 iFlow CLI 委托编排鉴权
系统 MUST 在 `/ui/engines` 提供 iFlow 连接入口，并支持 iFlow auth session 交互。

#### Scenario: 启动 iFlow 鉴权会话
- **WHEN** 用户点击“连接 iFlow”
- **THEN** UI 调用鉴权会话 start 接口（`engine=iflow`, `method=iflow-cli-oauth`）
- **AND** 页面展示会话状态与 URL（若已解析）

#### Scenario: 等待授权码时展示提交控件
- **WHEN** iFlow 会话状态为 `waiting_user`
- **THEN** 页面展示 authorization code 输入框与 submit 按钮
- **AND** 用户可提交 code 并进入后续状态

#### Scenario: 已鉴权启动后自动重入鉴权菜单
- **WHEN** iFlow 会话启动即出现主界面锚点
- **THEN** 后端自动注入 `/auth` 重入鉴权菜单
- **AND** UI 继续展示同一会话进展，不直接判定成功
