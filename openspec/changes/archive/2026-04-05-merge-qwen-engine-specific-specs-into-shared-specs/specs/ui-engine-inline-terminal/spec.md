## ADDED Requirements

### Requirement: Inline terminal sessions MAY enforce engine-declared session security policy
内嵌终端 capability MUST 允许引擎通过共享 session config 机制声明受限安全策略，而不是为单个 engine 维持专属 security capability。

#### Scenario: qwen inline terminal writes session-local enforced settings
- **WHEN** 用户从 `/ui/engines` 启动 Qwen inline terminal / UI shell
- **THEN** 系统 MUST 生成 session-local `.qwen/settings.json`
- **AND** 该文件 MUST 来自共享 config layering 与 adapter profile 声明的 config assets

#### Scenario: qwen inline terminal defaults to plan-style restricted permissions
- **WHEN** Qwen inline terminal session 配置被生成
- **THEN** 它 MUST 使用受限的 approval / permissions 默认值
- **AND** 它 MUST 禁止危险工具和未显式允许的高风险操作
