## Context

现有 runtime 合同已经把 `interaction.reply.accepted` 定义为 canonical FCMP 事件，并规定它负责把 run 从 `waiting_user` 推进到 `queued`。canonical chat replay 也已经基于该 FCMP 事件派生普通用户回复气泡。当前真正的实现缺口很窄：`submit_reply()` 虽然接受并持久化了 reply，也发起了续跑，但没有写出对应的 orchestrator event，因此 FCMP translator 看不到 reply-accepted 的源对象。

本 change 的设计目标不是引入第二条发布路径，而是把 reply acceptance 重新收敛到对称的 orchestrator 驱动发布模型中：先写 canonical orchestrator event，再翻译成 FCMP，最后由 chat replay 从 FCMP 派生用户气泡。

## Goals / Non-Goals

**Goals:**
- 通过 canonical 的 orchestrator-event-to-FCMP 路径恢复 `interaction.reply.accepted`。
- 保持 canonical chat replay 对普通用户回复气泡的来源仍然是 FCMP `interaction.reply.accepted`。
- 为 reply acceptance 增加 schema-backed 的 orchestrator event payload，使其与其他 orchestrator event 一样经过验证。
- 保持 shared SSOT、文档和 specs 与实现路径一致。

**Non-Goals:**
- 不为 chat replay 增加 interaction-history fallback。
- 不允许 reply endpoint 直接发布 `interaction.reply.accepted` FCMP。
- 不重做 chat replay、auth replay 或更大的 FCMP ordering 模型。
- 不新增 public API。

## Decisions

### 1. reply acceptance 统一经由 orchestrator event 发布
`submit_reply()` 在 reply 持久化成功、resume work 下发前，追加 canonical 的 orchestrator event `interaction.reply.accepted`。FCMP 的实际发布由 translator 负责，包括配对的 `conversation.state.changed(waiting_user -> queued, trigger=interaction.reply.accepted)`。

选择这个方案的原因：
- 它与现有 orchestrator 驱动的发布模型一致。
- schema 校验仍停留在 orchestrator event 层。
- canonical chat replay 继续只有一个 FCMP 真相源。

不采用的方案：
- 由 reply endpoint 直接发布 FCMP。这样会产生第二条发布路径，破坏 orchestrator-centric 的 runtime contract。

### 2. orchestrator event payload 承载 reply acceptance 元数据
新的 orchestrator event payload 至少包含 `interaction_id`、`accepted_at`、`response_preview`。这些字段足以支撑 FCMP translation 和 chat replay derivation，不需要暴露完整原始 response 对象。

选择这个方案的原因：
- 它提供了稳定、可校验的桥接对象。
- FCMP 的派生规则保持确定性。

不采用的方案：
- 之后再从 interaction history 反推 preview。这会重新引入第二条真相源。

### 3. canonical chat replay 对普通 reply 仍然只认 FCMP
本 change 不引入 interaction-history fallback。普通用户回复气泡只有在 FCMP `interaction.reply.accepted` 存在时才会出现。

选择这个方案的原因：
- 它保持 canonical replay 的单一真相源。
- 避免 live/history 分叉和 replay 歧义。

不采用的方案：
- 从 interaction history 回填 reply 气泡。这会削弱 chat replay 的 SSOT，并违背用户已确认的要求。

## Risks / Trade-offs

- [orchestrator event 与 FCMP translator 之间再次出现 schema 漂移] → 为 `interaction.reply.accepted` 增加 schema-registry 和 translator 回归测试。
- [reply acceptance preview 与 UI 既有展示格式不一致] → 保持 payload 最小化，并在 translator/chat replay 测试中复用同一套 preview 提取规则。
- [遗漏 paired `conversation.state.changed` 导致 resume 顺序回归] → translator 测试必须同时断言两条 FCMP 事件按预期出现。
- [该 change 与 canonical chat replay 现有假设发生偏差] → 同步更新相关 specs 和文档，明确 replay 仍是 FCMP 驱动，但 reply source publication 由 orchestrator 拥有。
