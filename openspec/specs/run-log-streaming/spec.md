# run-log-streaming Specification

## Purpose
TBD - created by archiving change run-observability-streaming-and-timeout. Update Purpose after archive.
## Requirements
### Requirement: 系统 MUST 在执行期间流式写入日志文件
系统 MUST 在 Agent 子进程执行过程中持续写入 stdout/stderr 到 run 目录日志文件，而不是仅在结束后写入。

#### Scenario: 进程执行中日志可见
- **WHEN** Agent 子进程正在运行并已产生部分输出
- **THEN** `data/runs/{run_id}/logs/stdout.txt` 或 `stderr.txt` 已包含阶段性内容
- **AND** 无需等待进程结束

#### Scenario: 日志文件初始化
- **WHEN** 新任务开始采集日志
- **THEN** 系统先清空上一轮同名日志文件内容
- **AND** 后续按流式 append 写入

### Requirement: 系统 MUST 保持失败归类语义
流式写盘改造 MUST 不改变现有 fail-fast 分类行为。

#### Scenario: 鉴权阻塞模式命中
- **WHEN** 输出中命中鉴权阻塞特征且任务超时/异常结束
- **THEN** 失败原因仍归类为 `AUTH_REQUIRED`

#### Scenario: 一般超时
- **WHEN** 未命中鉴权特征但触发硬超时
- **THEN** 失败原因归类为 `TIMEOUT`

