# engine-command-profile-defaults Specification

## Purpose
定义引擎命令行参数 profile 的默认值加载策略，区分 API 链路与 Harness 链路的参数注入行为。
## Requirements
### Requirement: API 链路 MUST 从配置文件加载引擎命令默认参数 Profile
系统 MUST 从 `server/assets/configs/engine_command_profiles.json` 读取并应用 API 链路的引擎命令默认参数 Profile。

#### Scenario: Profile 文件存在且引擎已配置
- **WHEN** API 链路为某引擎构建命令且 Profile 文件包含该引擎默认项
- **THEN** 系统按配置文件内容注入默认参数

#### Scenario: Profile 文件缺失或引擎未配置
- **WHEN** API 链路为某引擎构建命令但无可用 Profile 默认项
- **THEN** 系统使用空默认参数继续构建且不报错中断

### Requirement: Harness 链路 MUST NOT 注入 Profile 默认参数
系统 MUST 保证 Harness 命令构建不使用 Profile 默认参数，命令参数仅来源于用户透传与恢复所需最小上下文。

#### Scenario: Harness start 透传参数保持原样
- **WHEN** 用户通过 Harness 传入 start 透传参数
- **THEN** 命令构建不额外注入 Profile 默认参数

### Requirement: API 链路参数合并规则 MUST 稳定可预期
系统 MUST 定义 API 链路命令参数的稳定合并顺序，并保证显式调用参数优先级高于 Profile 默认参数。

#### Scenario: Claude headless profile defaults use JSON output mode
- **WHEN** Claude API 链路使用 profile 默认参数构建 start 或 resume 命令
- **THEN** profile 默认参数 MUST include `--output-format json`
- **AND** 该默认输出模式 MUST remain compatible with later native schema flag injection

#### Scenario: passthrough command bypasses profile-native schema injection
- **WHEN** builder receives explicit passthrough CLI args
- **THEN** command construction MUST preserve passthrough ownership
- **AND** it MUST NOT append native output schema flags automatically

### Requirement: Adapter profiles MUST declare structured-output governance strategy

Adapter profiles MUST declare structured-output behavior explicitly instead of relying on engine-name branching hidden inside command builders.

#### Scenario: profile declares structured-output strategy surface
- **WHEN** runtime loads an adapter profile
- **THEN** the profile MUST declare structured-output mode, CLI schema strategy, compatibility-schema strategy, prompt-contract strategy, and payload canonicalizer behavior
- **AND** profile validation MUST fail fast if those fields are malformed or contain invalid enum values

#### Scenario: profile gates schema CLI injection separately from command defaults
- **WHEN** an engine supports schema-constrained CLI execution
- **THEN** the profile MUST expose an explicit boolean gate for output-schema CLI injection
- **AND** disabling that gate MUST suppress schema CLI argument injection without changing the rest of the command defaults

