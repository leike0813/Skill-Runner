## ADDED Requirements

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
