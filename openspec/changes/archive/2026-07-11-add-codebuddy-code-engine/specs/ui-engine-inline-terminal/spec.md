## MODIFIED Requirements

### Requirement: 系统 MUST 采用每引擎单命令模型

系统 MUST 仅允许每个引擎一个 TUI 命令入口，不暴露 login/auth/version/interactive 多模式。CodeBuddy 使用同一入口，但必须通过独立 provider 选择门禁。

#### Scenario: 命令入口约束
- **WHEN** 用户从 UI 启动会话
- **THEN** 可选项包含 `codex`、`gemini`、`iflow`、`opencode`、`qwen`、`codebuddy` 等 capability 已启用引擎对应的唯一 TUI 命令
- **AND** 系统拒绝任何非白名单命令 ID

#### Scenario: 非 CodeBuddy 引擎携带 provider
- **WHEN** UI-shell start 为非 CodeBuddy 引擎提交 provider_id
- **THEN** 系统拒绝请求而不是静默忽略 provider

### Requirement: Inline terminal sessions MAY enforce engine-declared session security policy

内嵌终端 capability MUST 允许引擎通过共享 session config 机制声明受限安全策略，而不是为单个 engine 维持专属 security capability。

#### Scenario: CodeBuddy inline terminal writes session-local enforced settings
- **WHEN** 用户选择一个已登录 provider 并启动 CodeBuddy inline terminal
- **THEN** 系统 MUST 生成 session-local `.codebuddy/settings.json`
- **AND** 设置 MUST 来自 adapter profile 声明的共享 config layering assets
- **AND** 会话 snapshot 仅记录 provider_id，不得记录 token、user_id 或环境变量

#### Scenario: CodeBuddy inline terminal uses strict empty MCP
- **WHEN** CodeBuddy UI-shell launch plan 被生成
- **THEN** 系统 MUST 写入空 `mcpServers` 配置并传入 strict MCP 参数
- **AND** CLI MUST 使用 provider-scoped managed environment
