## ADDED Requirements

### Requirement: Run observation UI MUST support plain and bubble chat display modes
主 Run 观测 UI MUST 提供 `plain` 与 `bubble` 两种聊天展示模式，并默认使用 `plain`。

#### Scenario: run detail defaults to plain mode
- **WHEN** 用户打开 `/ui/runs/{request_id}`
- **THEN** 对话区默认使用 `plain` 模式
- **AND** 非终态 `assistant_message` MUST 直接显示为对话内容
- **AND** `assistant_process` / reasoning / tool / command 仍显示在过程视图中

#### Scenario: bubble mode keeps intermediate assistant message inside process region
- **WHEN** 用户切换到 `bubble` 模式
- **THEN** 非终态 `assistant_message` MUST 与 `assistant_process` 一起显示在过程区域
- **AND** 最终收敛消息仍按最终消息边界显示

### Requirement: Run observation mode switch MUST be presentation-only
Run 观测页面的 plain/bubble 切换 MUST 只影响渲染位置与分组，不得改变后端协议语义或消息身份。

#### Scenario: toggling mode preserves chat identity
- **WHEN** 用户在 `plain` 与 `bubble` 模式之间切换
- **THEN** 页面 MUST 复用同一份 canonical chat replay 数据
- **AND** MUST NOT 重新请求另一套专用协议或私有派生结果
