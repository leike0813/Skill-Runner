# run-log-streaming Specification

## Purpose
定义任务执行期间日志流式写入与读取的路径约定、写入语义和失败归类行为。

## Requirements
### Requirement: 系统 MUST 在执行期间流式写入日志文件
系统 MUST 在 Agent 子进程执行过程中持续写入 stdout/stderr 到 run 目录的 `.audit/` 子目录，而不是仅在结束后写入。

#### Scenario: 进程执行中日志可见
- **WHEN** Agent 子进程正在运行并已产生部分输出
- **THEN** `.audit/stdout.<N>.log`（`<N>` 为当前 attempt 编号）已包含阶段性内容
- **AND** 无需等待进程结束

#### Scenario: 多 attempt 日志独立
- **WHEN** 新 attempt 开始
- **THEN** 系统创建新的 `.audit/stdout.<N>.log` 文件
- **AND** 不覆盖或清空前序 attempt 的日志文件

### Requirement: 系统 MUST 保持失败归类语义
流式写盘改造 MUST 不改变现有 fail-fast 分类行为。

#### Scenario: 鉴权阻塞模式命中
- **WHEN** 输出中命中鉴权阻塞特征且任务超时/异常结束
- **THEN** 失败原因仍归类为 `AUTH_REQUIRED`

#### Scenario: 一般超时
- **WHEN** 未命中鉴权特征但触发硬超时
- **THEN** 失败原因归类为 `TIMEOUT`

