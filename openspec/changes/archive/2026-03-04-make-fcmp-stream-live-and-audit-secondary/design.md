# Design: make-fcmp-stream-live-and-audit-secondary

## Overview

本 change 将 runtime 协议流拆成四个明确职责：

- `LiveRuntimeEmitter`
  - 接收 adapter chunk，并把 chunk 喂给 parser live session
- `FcmpEventPublisher` / `RaspEventPublisher`
  - 负责分配 seq、附加关联元信息、写入 live journal
- `FcmpLiveJournal` / `RaspLiveJournal`
  - 负责活跃 run 的实时 replay 和 subscription
- `FcmpAuditMirrorWriter` / `RaspAuditMirrorWriter`
  - 负责把已发布事件异步镜像到 `.audit/*.jsonl`

batch `parse_runtime_stream()` / `build_rasp_events()` / `build_fcmp_events()` 不会删除，但降级为：

- 审计 backfill
- 旧 run / 进程重启后的冷回放
- parity tests

不再作为活跃 SSE 的 canonical 路径。

## Decision 1: FCMP live journal 是当前真相源

新增 `FcmpLiveJournal`：

- 以发布顺序保存 FCMP envelope
- 支持 `subscribe(run_id, after_seq)` 的 async 订阅
- 支持 `replay(run_id, after_seq)` 的内存回放
- terminal run 默认保留 15 分钟
- 单 run 默认最多保留 4096 条事件

规则：

- FCMP `seq` 在 publish 时分配
- `.audit/fcmp_events.*.jsonl` 不参与 live `seq` 分配
- 活跃 run 的 current truth 是 live journal，而不是 audit file

## Decision 2: RASP 也 live publish，但默认不直接暴露给前端

新增 `RaspLiveJournal`：

- 保存 parser/orchestration 已发布的 RASP 事件
- 保留顺序和关联信息
- 支撑审计镜像与管理回放

RASP `seq` 仍保持 attempt 内局部单调，避免破坏现有管理端 `stream=rasp` 语义。  
RASP 的 canonical 顺序由 live parser emission 顺序决定，而不是由文件写入时间决定。

## Decision 3: FCMP 与 RASP 共享同一个增量解析入口

新增 `LiveStreamParserSession`：

- `feed(stream, text, byte_from, byte_to) -> list[LiveParserEmission]`
- `finish(exit_code, failure_reason) -> list[LiveParserEmission]`

新增 `LiveRuntimeEmitter`：

- 按 chunk 调用 parser live session
- 将 emission 同时翻译为 FCMP / RASP
- 发布到 live journal
- 将已发布事件异步提交给 audit mirror writer

边界：

- parser 只负责识别语义
- publisher 只负责 publish / seq / correlation
- mirror writer 只负责 append

## Decision 4: FCMP 与 RASP 的关联显式化

所有 live emission 派生出的 FCMP / RASP 共享：

- `correlation.publish_id`

这保证：

- `assistant.message.final` 可与对应 RASP `agent.message.final` 建立稳定关联
- raw 行、诊断、assistant 最终消息、状态迁移不会再靠“时间接近”去猜

## Decision 5: SSE 改成 memory-first subscription

`iter_sse_events()` 新流程：

1. 读取 `.state/state.json`，发送 `snapshot`
2. 从 `FcmpLiveJournal.replay()` 回放 cursor 之后的事件
3. 若 cursor 早于内存下限，则补 audit fallback
4. 订阅 live journal，实时推送新事件
5. 收到 terminal FCMP 事件并排空队列后关闭

不再使用：

- 轮询 `list_event_history()`
- `_materialize_protocol_stream()`
- “等 FCMP 文件物化”的 trailing drain

## Decision 6: `/events/history` 改为 memory-first + audit-fallback

history 返回新增 metadata：

- `source: live | audit | mixed`
- `cursor_floor`
- `cursor_ceiling`

规则：

- 活跃 / 近期 run 优先读 journal
- journal 缺口再回退到 audit
- 进程重启后 journal 不存在时，完整回退到 audit
- merge 时按 FCMP `seq` 去重，live 优先

## Decision 7: orchestration-originated FCMP 走 shared publisher

以下事件不再依赖事后 `build_fcmp_events()`：

- `conversation.state.changed`
- `interaction.reply.accepted`
- `auth.completed`
- `conversation.completed`
- `conversation.failed`

它们统一通过 `FcmpEventPublisher.publish(...)` 进入 live timeline，和 parser-originated FCMP 共享同一 `seq` 时间线。

## Decision 8: engine parser 渐进式增量化

引擎 parser 实现策略：

- codex / opencode
  - 支持基于 NDJSON 行的 live session，尽可能在 `item.completed` / `text` 出现时就吐出 assistant emission
- gemini
  - 支持 chunk accumulate + finish flush；若行内完整 JSON 已经出现，可提前发
- iflow
  - 初期允许主要在 `finish()` 产出 assistant emission，但 raw/diagnostic 仍 live 化

这保证本次 change 可以先把 live publish 的架子打通，同时不要求所有 parser 一步到位实现完美逐 token 语义增量。

## Migration Strategy

### Phase A

- 引入 live journals / publishers / mirror writers
- SSE / history 先切到 FCMP live path
- adapter `_capture_process_output()` 接入 `LiveRuntimeEmitter`

### Phase B

- 各 parser 增加 live session
- RASP history 逐步接入 memory-first
- batch materialization 保留为 fallback/backfill

## Risks and Mitigations

- 风险：live journal 与 audit fallback 出现重复事件
  - 方案：按 `seq` 去重，live 优先
- 风险：旧 parser 尚未实现真正增量语义
  - 方案：允许 `finish()` 才吐 assistant emission，但仍不依赖 audit
- 风险：进程重启后内存 journal 丢失
  - 方案：history 与 reconnect 回退到 audit
