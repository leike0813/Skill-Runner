## ADDED Requirements

### Requirement: Harness MUST 复用 Adapter 命令构建接口
系统 MUST 使 Harness 的 start/resume 执行路径调用与主服务相同的 Adapter 命令构建接口，禁止在 Harness 内维护独立命令拼接分支。

#### Scenario: Harness start 走 Adapter
- **WHEN** Harness 执行 start 命令
- **THEN** 系统通过 Adapter 接口生成最终命令数组

#### Scenario: Harness resume 走 Adapter
- **WHEN** Harness 执行 resume 命令并带 handle/message
- **THEN** 系统通过 Adapter resume 接口生成最终命令数组

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
