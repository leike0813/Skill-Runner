## MODIFIED Requirements

### Requirement: 系统 MUST 采用每引擎单命令模型
系统 MUST 仅允许每个引擎一个 TUI 命令入口，不暴露 login/auth/version/interactive 多模式。

#### Scenario: 命令入口约束
- **WHEN** 用户从 UI 启动会话
- **THEN** 可选项仅为 `codex`、`gemini`、`iflow`、`opencode` 对应 TUI 命令
- **AND** 系统拒绝任何非白名单命令 ID
