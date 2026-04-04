# single-worker-hotpath-async-audit-and-auth-windowing Design

## Design Overview

这次 change 的设计目标是把运行时主路径重新收敛为：

1. subprocess 输出读取与 live journal 发布优先
2. audit 落盘退到后台串行 writer
3. auth detection 只看最近窗口，且低频触发
4. slot 释放不等待 audit drain

这样可以在不改外部协议的前提下，最大限度降低单 worker 事件循环饥饿。

## Buffered Async Audit Writers

新增共享组件：

- `BufferedAsyncTextFileWriter`

行为固定为：

- 每个审计文件对应一个单消费者 writer
- 主路径只做 `enqueue(text)`，不做同步 `flush`
- writer 在后台任务中按批次写盘
- 队列按字节有界；超限时允许丢弃 audit 写入，但不得反向阻塞 live 主链路

这一模式覆盖：

- `stdout.{attempt}.log`
- `stderr.{attempt}.log`
- `io_chunks.{attempt}.jsonl`
- `fcmp_events.{attempt}.jsonl`
- `events.{attempt}.jsonl`
- `chat_replay.jsonl`

live journal 仍然先同步发布，保证运行中 history live-first 路径不依赖 audit 文件完整性。

## Low-Frequency Windowed Auth Detection

auth detection 从“全文 join + 高频 parse”改为：

- `stdout` 最近 `64 KiB` 窗口
- `stderr` 最近 `16 KiB` 窗口
- `AUTH_DETECTION_PROBE_THROTTLE_SECONDS = 1.5`
- 只有当节流窗口已过且期间确实出现新输出时才触发 probe
- 进程结束前保留一次 `force=True` 终态 probe 兜底

这保证：

- probe 成本近似常数
- 大 `tool_result` / verbose 输出不再反复把 parser 拖进 O(n) 路径
- auth 提示仍可被检测，只是允许比旧实现略晚

## Slot Release And Drain Decoupling

本次最重要的容量约束是：

- subprocess 退出后，slot 释放优先
- audit writer drain 不得成为 slot release 的前置条件

实现上采用：

- run 主路径完成 reader 收口后，立即释放 `process_supervisor` / active process 跟踪
- audit writer 只做一个严格有上限的 best-effort drain
- 默认 drain 预算为 `200ms`
- 超过预算则继续后台完成，不阻塞 run lifecycle 的返回

这样不会改变 `ConcurrencyManager` 的公式，也尽量不改变 effective concurrency。

## Terminal Observability Coordination

terminal run 的 protocol history 读取新增轻量协调：

- 先尝试对 FCMP/RASP/chat replay mirror 做 bounded flush
- 若在预算内完成，则继续使用 audit-first 终态路径
- 若未完成，则 terminal 读路径退回 live-first，不同步等待 audit 完整

这允许 run 已完成但 audit 仍在追写的短窗口内，页面读取仍然快速返回。

## Raw Output Accumulation

运行时不再维护 `stdout_chunks/stderr_chunks` 这种需要末尾 `join` 的 list 模型，而改为：

- 单一增量缓冲用于最终 `raw_stdout/raw_stderr`
- 最近窗口用于 auth detection

这样既消除了运行中的反复 `join`，也消除了结束时的一次性大 `join`。

## Compatibility

- 不新增 HTTP API
- 不修改 FCMP / RASP / chat replay 事件结构
- 不改变 UI 协议与轮询参数
- 允许 audit 文件比 live journal 轻微滞后，但最终仍会收敛
