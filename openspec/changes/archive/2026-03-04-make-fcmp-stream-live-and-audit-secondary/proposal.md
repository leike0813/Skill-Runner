# Proposal: make-fcmp-stream-live-and-audit-secondary

## Why

当前 runtime 事件链路把 `.audit/fcmp_events.<attempt>.jsonl` 当成活跃会话的真相源：

- adapter 先把 stdout/stderr 写入审计日志
- observability 再从审计日志重建 RASP / FCMP
- SSE 与 `/events/history` 再去读取重建后的 FCMP 文件

这导致几个持续复现的问题：

- 最后一条 `assistant.message.final` 往往只能刷新后看到
- `waiting_user` / `waiting_auth` 提示可能进入状态机，但聊天记录里看不到对应消息
- SSE 的正确性取决于审计文件何时物化，而不是取决于事件何时被解析出来
- 前端不得不用 reconnect / catch-up / terminal draining 来掩盖后端真相链路倒置的问题

同时，RASP 目前也主要依赖事后重建。如果 FCMP 进入 live publish，而 RASP 仍停留在 audit-first 模式，那么二者的相对顺序、`raw_ref` 证据链和回放关联都会继续漂移。

## What Changes

本 change 将把 runtime 事件体系重构为“先发布，后镜像”：

1. adapter 在运行过程中按 chunk 暴露原始输出
2. parser 以增量 session 的方式消费 chunk
3. parser 一旦识别出语义事件，立刻发布 FCMP / RASP
4. SSE 直接订阅 live journal，而不是轮询已物化文件
5. `/events/history` 对活跃与近期 run 采用 memory-first、audit-fallback
6. `.audit/fcmp_events.*.jsonl` 与 `.audit/events.*.jsonl` 降级为审计镜像与冷回放来源

## Scope

### In Scope

- FCMP live publish 与内存 journal
- RASP live publish 与顺序定义
- adapter chunk 级输出上报
- parser 增量 session 合同
- SSE / history 的 memory-first replay
- 审计镜像的异步落盘职责
- 相关 schema / invariants / specs / docs / tests

### Out of Scope

- 改写 run state machine
- 把 RASP 暴露为新的前端业务协议
- 重做 auth / reply / waiting 的业务语义
- 改变 `.state/state.json` 和 `result/result.json` 的主职责

## Success Criteria

- 最后一条 `assistant.message.final` 的实时显示不再依赖 `.audit/fcmp_events.*.jsonl`
- 活跃 run 的 SSE 不再触发 `_materialize_protocol_stream()` 作为前置
- `/events/history` 可优先从内存 journal 回放近期事件
- FCMP 与 RASP 都按 live publish 的顺序生成并可稳定关联
- 审计文件保留完整历史，但不再阻塞实时分发
