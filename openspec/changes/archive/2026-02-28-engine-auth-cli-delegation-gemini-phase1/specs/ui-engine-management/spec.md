## ADDED Requirements

### Requirement: Engine 管理页 MUST 支持 Gemini CLI 委托编排鉴权
系统 MUST 在 `/ui/engines` 提供 Gemini 连接入口，并支持提交 authorization code 的会话交互。

#### Scenario: 启动 Gemini 鉴权会话
- **WHEN** 用户点击“连接 Gemini”
- **THEN** UI 调用鉴权会话 start 接口（`engine=gemini`）
- **AND** 页面展示当前会话状态

#### Scenario: 等待授权码时展示提交控件
- **WHEN** 会话状态为 `waiting_user_code`
- **THEN** 页面展示 authorization code 输入框与 submit 按钮
- **AND** 用户可提交 code 进入下一状态

#### Scenario: 启动即已在主界面时自动 re-auth
- **WHEN** Gemini 会话启动后直接出现主界面锚点
- **THEN** 后端自动发送 `/auth login`
- **AND** UI 继续展示本轮鉴权会话状态，不直接判定成功

