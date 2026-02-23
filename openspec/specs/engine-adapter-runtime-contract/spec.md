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

### Requirement: 系统 MUST 提供 opencode 临时 Adapter 占位
系统 MUST 提供 `opencode` 的临时 Adapter，实现可迁移的 runtime 流解析能力；对尚未实现的执行能力必须返回结构化 capability unavailable 错误。

#### Scenario: opencode 执行能力未实现
- **WHEN** 调用方请求 opencode 执行命令构建或执行且该能力尚未实现
- **THEN** 系统返回结构化 `ENGINE_CAPABILITY_UNAVAILABLE` 错误

#### Scenario: opencode 流解析仍可用
- **WHEN** 协议层请求 opencode Adapter 解析运行日志
- **THEN** Adapter 返回标准化 runtime 解析结构用于事件组装

