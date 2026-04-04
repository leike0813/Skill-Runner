# runtime-utf8-stream-decoding-integrity Design

## Design Overview

本次 change 的核心是把“文本真相”统一建立在原始 `io_chunks` bytes 之上：

1. `io_chunks`
   - 继续作为原始字节 SSOT
   - 写入顺序与文件格式不变
2. 增量 UTF-8 decoder
   - 在 execution 与 strict replay 两条路径上共享
   - 保证跨 chunk 的合法多字节字符不会被拆坏
3. 文本消费者
   - `stdout/stderr.log`
   - `stdout_chunks/stderr_chunks`
   - `live_runtime_emitter.on_stream_chunk(...)`
   - strict replay rows 的 `text`

这些消费者都必须消费同一份“增量解码后的文本”。

## Shared Incremental Decoder

新增公共 helper：

- `IncrementalUtf8TextDecoder`

行为固定为：

- `feed(chunk: bytes) -> str`
  - 接受原始 bytes
  - 返回本次新增的文本片段
- `finish() -> (tail_text, pending_len)`
  - flush 尾部残留状态
  - 返回最终文本片段与 final flush 前仍挂起的原始字节数

decoder 采用 UTF-8 replacement 语义，因此：

- 合法但跨 chunk 的字符会在后续 chunk 到达时正确恢复
- 真正无效的字节仍会得到 replacement
- 不再因为 chunk 边界额外制造 replacement

## Execution Path Integration

`base_execution_adapter._capture_process_output()` 中：

- `stdout` / `stderr` 各自维护一个 decoder
- 每个原始 chunk 仍先写入 `io_chunks`
- 再将 decoder 产出的文本写入：
  - `stdout/stderr.log`
  - `stdout_chunks/stderr_chunks`
  - `live_runtime_emitter.on_stream_chunk(...)`
- EOF 时 flush decoder，并把尾部文本继续送入上述同一条链路

这样 `stdout.log` 与 live parser 输入都等价于：

- “将整条原始字节流一次性按 UTF-8 replacement 解码”的结果

## Strict Replay Integration

`run_observability._load_io_chunks_for_strict_replay()` 中：

- 对 `stdout` / `stderr` 分别维护 decoder
- 按 `seq` 顺序对 `payload_b64` 解码后的 bytes 做增量解码
- replay row 的 `text` 使用 decoder 输出，而不是逐 chunk `decode(..., replace)`
- replay 结束时 flush decoder，并把尾部文本并入该 stream 的最后一条 replay row

这样 strict replay 驱动的 parser 将看到与 execution 热路径相同的文本真相。

## Compatibility

- 不新增 FCMP / RASP / chat replay 类型
- 不修改 `raw_ref.byte_from/byte_to`
- `stdout/stderr.log` 的内容会比旧实现更接近真实 UTF-8 文本，但不保证字节可逆
- `io_chunks` 继续是唯一原始字节真相源
