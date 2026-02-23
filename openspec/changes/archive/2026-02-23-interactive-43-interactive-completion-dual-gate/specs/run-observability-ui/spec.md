## MODIFIED Requirements

### Requirement: Run 页面 MUST 支持对话窗口式管理体验
The Run page MUST activate waiting-user interactions from status and pending/protocol events, and MUST NOT depend on ask_user JSON blocks embedded in assistant text.

#### Scenario: waiting_user 交互来源稳定
- **WHEN** Run 状态进入 `waiting_user`
- **THEN** 页面通过 pending 接口或 `user.input.required` 事件激活输入框
- **AND** 不要求 assistant 消息中出现结构化 ask_user 文本

#### Scenario: assistant 文本中的 ask_user 块仅作展示
- **WHEN** assistant 消息正文包含 ask_user-like JSON 文本
- **THEN** 页面将其视为普通消息内容
- **AND** 不据此单独驱动交互状态机

#### Scenario: 软条件完成告警可见
- **WHEN** 后端以软条件完成 interactive run
- **THEN** 页面展示 `INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER` 诊断告警
- **AND** 不影响 completed 状态展示

#### Scenario: 超轮次失败原因可见
- **WHEN** interactive run 因 `max_attempt` 触发失败
- **THEN** 页面展示 `INTERACTIVE_MAX_ATTEMPT_EXCEEDED` 失败原因
