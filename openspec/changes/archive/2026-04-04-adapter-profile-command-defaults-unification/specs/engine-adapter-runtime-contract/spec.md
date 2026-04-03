## MODIFIED Requirements

### Requirement: Adapter Profile MUST 承载命令默认参数合同
每个引擎的 adapter profile MUST 声明 `command_defaults.start`、`command_defaults.resume` 与 `command_defaults.ui_shell`，作为该引擎命令默认参数的单一来源。

#### Scenario: adapter profile 缺少 command defaults
- **WHEN** 任一引擎 `adapter_profile.json` 缺少 `command_defaults` 或其子字段
- **THEN** adapter profile 校验 MUST fail-fast
- **AND** 服务不得进入可运行状态

### Requirement: CommandBuilder MUST 只负责骨架命令与运行时变量参数
每个引擎的 CommandBuilder MUST 从 adapter profile 读取默认参数，并只负责拼接可执行路径、resume/session 参数及运行时显式参数。

#### Scenario: Claude start 命令构建
- **WHEN** Claude adapter 构建 start 命令
- **THEN** `-p --output-format stream-json --verbose --settings .claude/settings.json` 来自 `command_defaults.start`
- **AND** builder 不再硬编码这些默认参数
