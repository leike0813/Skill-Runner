## MODIFIED Requirements

### Requirement: 示例客户端 MUST 支持交互式对话直到终态
示例客户端 MUST 以终端用户对话体验为中心，且保持 FCMP 语义一致。

#### Scenario: Ask User YAML 转提示卡
- **WHEN** `assistant.message.final` 文本包含 `<ASK_USER_YAML>` 或 fenced `ask_user_yaml`
- **THEN** 客户端提取结构化字段并更新提示卡
- **AND** YAML 原文不作为聊天气泡正文展示

#### Scenario: user.input.required 归类为 Agent 问询
- **WHEN** 收到 `user.input.required` 事件
- **THEN** 客户端将其展示为 Agent 侧问询语义（非 System）
- **AND** 与提示卡按 `interaction_id + prompt` 去重

#### Scenario: 终态产物摘要消息
- **WHEN** run 进入终态且存在 artifacts
- **THEN** 客户端追加一条 Agent 侧产物摘要消息
- **AND** 不移除已有 `assistant.message.final` 消息

### Requirement: 示例客户端观察页 MUST 去除技术噪音面板
示例客户端观察页 MUST 仅保留对话与基础状态，不展示后台诊断细节面板。

#### Scenario: 页面元素裁剪
- **WHEN** 用户访问 `/runs/{request_id}`
- **THEN** 页面不展示 `stderr`、`diagnostics`、`Event Relations`、`Raw Ref Preview` 面板
- **AND** 页面保留对话列表、提示卡、回复输入区与状态信息

### Requirement: 示例客户端回复输入 MUST 支持快捷键发送
示例客户端 MUST 支持键盘快捷发送并在界面明确提示。

#### Scenario: Ctrl/Cmd + Enter 发送
- **WHEN** 用户在回复输入框按下 `Ctrl+Enter` 或 `Cmd+Enter`
- **THEN** 客户端触发与点击发送按钮等价的 reply 提交行为
- **AND** 按钮右侧展示快捷键提示文本
