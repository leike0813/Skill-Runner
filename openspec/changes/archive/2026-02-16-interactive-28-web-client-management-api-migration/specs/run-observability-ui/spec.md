## ADDED Requirements

### Requirement: Run 页面 MUST 支持对话窗口式管理体验
系统 MUST 让内建 Run 页面在统一管理接口下支持对话窗口所需能力：实时输出、交互回复、文件浏览。

#### Scenario: waiting_user 交互
- **WHEN** Run 状态进入 `waiting_user`
- **THEN** 页面展示 pending 信息
- **AND** 允许用户提交 reply 并恢复执行

#### Scenario: 实时输出观测
- **WHEN** Run 状态为 `running`
- **THEN** 页面消费 SSE 输出事件并实时更新 stdout/stderr 显示
- **AND** 断线后可续传恢复

#### Scenario: 用户主动终止
- **WHEN** 用户在 Run 页面触发 cancel
- **THEN** 页面调用 management API 的 cancel 动作
- **AND** 页面状态收敛到 `canceled` 并停止继续交互
