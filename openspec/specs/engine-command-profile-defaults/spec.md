# engine-command-profile-defaults Specification

## Purpose
TBD - created by archiving change interactive-42-engine-runtime-adapter-decoupling. Update Purpose after archive.
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

#### Scenario: 显式参数覆盖默认参数
- **WHEN** API 请求参数与 Profile 默认参数存在同名冲突
- **THEN** 生成命令中保留显式参数取值并覆盖默认值

