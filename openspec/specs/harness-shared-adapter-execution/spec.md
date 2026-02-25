# harness-shared-adapter-execution Specification

## Purpose
TBD - created by archiving change interactive-42-engine-runtime-adapter-decoupling. Update Purpose after archive.
## Requirements
### Requirement: Harness MUST 复用 Adapter 命令构建接口
系统 MUST 使 Harness 的 start/resume 执行路径调用与主服务相同的 Adapter 命令构建接口，禁止在 Harness 内维护独立命令拼接分支。  
Harness 还 MUST 将 execution mode 作为运行上下文的一部分贯通到配置注入与技能补丁注入链路：
- start 未指定 `--auto` 时使用 `interactive`
- start 指定 `--auto` 时使用 `auto`
- resume 时优先继承 handle metadata 中的 execution mode，缺失时回退 `interactive`

#### Scenario: start 默认 interactive 并走 Adapter
- **WHEN** Harness 执行 start 且未指定 `--auto`
- **THEN** 系统通过 Adapter 接口生成最终命令数组
- **AND** 本次 attempt 的配置注入与技能补丁注入按 `execution_mode=interactive` 执行

#### Scenario: start 指定 --auto 并走 Adapter
- **WHEN** Harness 执行 start 且指定 `--auto`
- **THEN** 系统通过 Adapter 接口生成最终命令数组
- **AND** 本次 attempt 的配置注入与技能补丁注入按 `execution_mode=auto` 执行

#### Scenario: resume 继承已记录 execution mode
- **WHEN** Harness 执行 resume 且 handle metadata 含 execution mode
- **THEN** 系统通过 Adapter resume 接口生成最终命令数组
- **AND** 本次 resume attempt 继续使用 handle 中记录的 execution mode

### Requirement: Harness MUST 复用 Adapter runtime 解析接口
系统 MUST 使 Harness 的运行日志解析调用 Adapter runtime 解析接口，并复用统一协议层生成 RASP/FCMP 事件与报告。

#### Scenario: Harness 生成协议事件
- **WHEN** Harness 收集到一次 attempt 的 stdout/stderr/pty 日志
- **THEN** 系统调用 Adapter runtime 解析并输出统一事件与报告

### Requirement: Harness MUST 保持 translate 控制参数不透传
系统 MUST 将 `--translate 0|1|2|3` 仅作为 Harness 视图控制参数，且不得透传到引擎命令参数中。

#### Scenario: translate 参数隔离
- **WHEN** 用户在 Harness 中指定 `--translate`
- **THEN** 该参数只影响输出渲染层级，不出现在最终引擎命令数组中

