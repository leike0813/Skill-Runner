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

### Requirement: 系统 MUST 并行写入 stdout/stderr chunk journal
系统 MUST 在执行期间将 stdout/stderr 的每个读取 chunk 以无损形式写入 `.audit/io_chunks.<attempt>.jsonl`，并与明文日志并行存在。

#### Scenario: running attempt writes readable log and chunk journal
- **WHEN** attempt 执行中产生 stdout/stderr 输出
- **THEN** `.audit/stdout.<N>.log` 与 `.audit/stderr.<N>.log` 持续追加
- **AND** `.audit/io_chunks.<N>.jsonl` 也持续追加
- **AND** 每条 chunk 记录包含 `seq/ts/stream/byte_from/byte_to/payload_b64/encoding`

### Requirement: chunk journal payload MUST be reversible
chunk journal 中 `payload_b64` MUST 可还原为原始 bytes，以支持协议重构。

#### Scenario: decode payload_b64
- **WHEN** 读取 `io_chunks` 并按 `payload_b64` 解码
- **THEN** 拼接结果 MUST 与对应 stream 原始输出字节一致

### Requirement: strict replay evidence MUST preserve uploads-relative file references
The runtime audit and rebuild contract MUST preserve enough information to replay declarative file-input references and resolved artifact paths.

#### Scenario: request payload records declarative file input
- **WHEN** a run is created with file input paths in the request body
- **THEN** the request snapshot preserves those values for audit and rebuild purposes
