## MODIFIED Requirements

### Requirement: API 链路 MUST 从 Adapter Profile 加载引擎命令默认参数
系统 MUST 从各引擎 `server/engines/<engine>/adapter/adapter_profile.json` 的 `command_defaults` 字段读取并应用 API 链路的命令默认参数。

#### Scenario: Adapter Profile 声明 start 默认参数
- **WHEN** API 链路为某引擎构建 start 命令且 `command_defaults.start` 有值
- **THEN** 系统按该字段内容注入默认参数

#### Scenario: Adapter Profile 声明 resume 默认参数
- **WHEN** API 链路为某引擎构建 resume 命令且 `command_defaults.resume` 有值
- **THEN** 系统按该字段内容注入默认参数

### Requirement: 独立 command profile 文件 MUST NOT 再作为合同来源
系统 MUST NOT 再读取或依赖独立 `command_profile.json` 或集中 `engine_command_profile.py` 作为命令默认参数来源。

#### Scenario: 运行时读取命令默认参数
- **WHEN** 任一 adapter 或 UI shell provider 需要读取默认命令参数
- **THEN** 参数来源仅为 `AdapterProfile.command_defaults`

### Requirement: UI shell 默认参数 MUST 与 adapter profile 同源
系统 MUST 从 `command_defaults.ui_shell` 读取 UI shell 的默认启动参数。

#### Scenario: UI shell 构建默认 launch args
- **WHEN** 管理 UI 进入某引擎的 inline shell
- **THEN** 启动参数来自该引擎 `adapter_profile.json` 的 `command_defaults.ui_shell`
