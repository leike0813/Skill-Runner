# single-worker-hotpath-async-audit-and-auth-windowing Proposal

## Summary

修复单 worker 运行时在高频输出场景下出现的“假死”问题，把最重的同步热路径从主事件循环中剥离，同时保持当前并发容量语义不变。

本次 change 聚焦三件事：

- 运行时 audit 写盘改为真正后台化
- auth detection 改为低频增量窗口探测
- slot 释放与 audit drain 解耦，避免有效并发缩水

## Motivation

当前运行中出现页面刷新长时间转圈、RASP/FCMP 停滞、chat 与协议流节奏分裂的一个高概率主因是：

- `stdout/stderr` chunk 热路径内存在同步 `write + flush`
- FCMP/RASP/chat replay audit mirror 仍会在事件循环里做同步落盘
- auth detection 反复对累计全文做 `join + parse_runtime_stream`

在单 worker `uvicorn` 模型下，这些路径会直接抢占同一个事件循环，导致 UI/API 看起来像“卡死”。同时如果把 audit drain 串到 run lifecycle 主路径，还会延长 slot 占用时间，降低 effective concurrency。

## Scope

- 为 runtime audit 面引入后台 writer 队列
- 让 `stdout.log`、`stderr.log`、`io_chunks`、FCMP/RASP/chat replay mirror 走异步落盘
- 将 auth detection 改成低频、窗口化 probe
- 保证 slot 释放不等待 audit drain
- 在 terminal observability 上允许 live-first fallback，避免为了等 audit 完整而同步卡住

## Non-Goals

- 不修改 FCMP / RASP / chat 的外部事件类型
- 不修改 UI 请求形状与轮询协议
- 不在本次 change 中顺手修 terminal fallback / result-file fallback / dispatch-state 其它异常
- 不改变 `ConcurrencyManager` 的容量公式

## Capabilities

### Modified Capabilities

- `engine-adapter-runtime-contract`
