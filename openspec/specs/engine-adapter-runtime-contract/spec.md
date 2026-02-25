# engine-adapter-runtime-contract Specification

## Purpose
TBD - created by archiving change interactive-42-engine-runtime-adapter-decoupling. Update Purpose after archive.
## Requirements
### Requirement: Adapter MUST 提供统一运行时命令构建接口
系统 MUST 为所有引擎 Adapter 提供统一的命令构建契约，至少覆盖 start 与 resume 两类执行入口，并允许调用方显式指定是否启用 API 默认 Profile 参数。

#### Scenario: API 链路构建 start 命令
- **WHEN** 后端 API 编排层请求构建某引擎 start 命令且声明启用 Profile
- **THEN** Adapter 返回可执行命令数组并应用该引擎 Profile 默认参数

#### Scenario: Harness 链路构建 start 命令
- **WHEN** Harness 请求构建某引擎 start 命令且声明禁用 Profile
- **THEN** Adapter 返回仅基于透传参数与必要上下文的命令数组

### Requirement: Adapter MUST 提供统一 runtime 流解析接口
系统 MUST 要求所有引擎 Adapter 提供 runtime 流解析接口，输出统一结构字段（parser、confidence、session_id、assistant_messages、raw_rows、diagnostics、structured_types）。

#### Scenario: 引擎流解析返回标准字段
- **WHEN** 任何引擎 Adapter 解析 stdout/stderr/pty 原始字节流
- **THEN** 返回值包含统一结构字段并可直接被协议层消费

### Requirement: 系统 MUST 提供 opencode 正式 Adapter 执行能力
系统 MUST 提供 `opencode` 的正式 Adapter，覆盖 start/resume 命令构建、执行生命周期与 runtime 流解析，并在 interactive 场景支持 `session` 续跑。

#### Scenario: opencode 配置组装包含 enforce 层
- **WHEN** Adapter 构建 opencode 运行时项目级配置
- **THEN** MUST 按统一优先级合并 `engine_default -> skill defaults -> runtime overrides -> enforced`
- **AND** `server/assets/configs/opencode/enforced.json` MUST 作为强制覆盖层生效

#### Scenario: opencode auto 模式权限策略
- **WHEN** `execution_mode=auto`
- **THEN** Adapter 写入的项目级配置 MUST 包含 `"permission.question":"deny"`

#### Scenario: opencode interactive 模式权限策略
- **WHEN** `execution_mode=interactive`
- **THEN** Adapter 写入的项目级配置 MUST 包含 `"permission.question":"allow"`

