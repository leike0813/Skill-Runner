## ADDED Requirements

### Requirement: Windows cli_delegate MUST be platform-capability gated at bootstrap
系统在 Windows 上 MUST 在启动期检测 `pywinpty` 能力，并基于检测结果决定 `cli_delegate` 路由是否可用。  
当能力缺失时，系统 MUST 禁用受影响引擎的 `cli_delegate` 路由并保留 `oauth_proxy` 路由。

#### Scenario: pywinpty unavailable on Windows
- **GIVEN** runtime platform is Windows
- **AND** `pywinpty` import or required symbols are unavailable
- **WHEN** 系统构建 auth driver registry
- **THEN** `gemini/iflow/opencode` 的 `cli_delegate` 组合 MUST NOT 被注册
- **AND** `oauth_proxy` 组合 MUST remain available
- **AND** 系统 MUST 输出可操作 warning 日志

#### Scenario: pywinpty available on Windows
- **GIVEN** runtime platform is Windows
- **AND** `pywinpty` capability check passes
- **WHEN** 系统构建 auth driver registry
- **THEN** `gemini/iflow/opencode` 的 `cli_delegate` 组合 MUST be registered
- **AND** 既有 `oauth_proxy` 行为 MUST remain unchanged

### Requirement: cli_delegate PTY runtime MUST be cross-platform unified
`gemini/iflow/opencode` 的 `cli_delegate` 驱动 MUST 通过共享 PTY 适配层启动与读写终端，避免直接依赖平台专属模块导致导入崩溃。

#### Scenario: Windows flow startup
- **GIVEN** runtime platform is Windows
- **WHEN** `cli_delegate` auth session starts
- **THEN** 驱动 MUST 通过共享 PTY 适配层启动进程并读取终端输出
- **AND** 不得因 `pty/termios` 导入失败中断服务启动

#### Scenario: POSIX flow startup
- **GIVEN** runtime platform is Linux/macOS
- **WHEN** `cli_delegate` auth session starts
- **THEN** 驱动 MUST 保持现有 POSIX PTY 语义
- **AND** 会话状态机行为 MUST remain unchanged
