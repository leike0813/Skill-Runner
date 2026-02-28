## MODIFIED Requirements

### Requirement: UI auth behavior remains unchanged while auth runtime is modularized
phase2 期间，管理 UI 鉴权交互与状态展示 MUST 保持兼容，不因内部 runtime 重组而改变用户操作路径。

#### Scenario: UI starts auth session
- **WHEN** 用户在 `/ui/engines` 发起鉴权
- **THEN** 返回状态字段与状态推进语义保持不变
- **AND** 运行中锁行为（禁止并发 auth/TUI）保持不变

#### Scenario: UI cancels auth session
- **WHEN** 用户取消会话
- **THEN** 会话进入 `canceled` 终态
- **AND** 后续可再次发起鉴权（锁已释放）
