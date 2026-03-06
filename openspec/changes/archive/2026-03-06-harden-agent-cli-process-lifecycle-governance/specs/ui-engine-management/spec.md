## ADDED Requirements

### Requirement: UI Inline TUI 进程 MUST 纳入统一 lease 治理
UI shell 启动的 ttyd/CLI 进程 MUST 注册 lease；会话停止或终态清理 MUST 释放 lease；终止路径 MUST 使用统一终止器。

#### Scenario: 停止 UI TUI 会话
- **WHEN** 用户主动停止 inline TUI
- **THEN** 系统统一终止受管进程
- **AND** lease 被关闭
