## Context

当前交互链路把“非终态但已面向用户的 agent 文本”近似塞进了 `reasoning / assistant_process` 语义，然后在回合收敛时再通过 `promoted/final` 把其中一部分转成正式 assistant 消息。这种做法把两类本来不同的内容混在了一起：
- 真正的推理过程，仍然属于过程语义；
- 已经接近终端 plain 输出风格、但尚未终态收敛的 agent 文本，本质上更像对话内容。

结果是协议层语义不清，canonical chat replay 需要做额外 promote/dedupe，前端默认只能用 thinking bubble 承载大量 agent 文本，显示面积和阅读体验都受到限制。这个 change 需要同时调整 runtime 语义、chat replay 派生以及两个前端的展示模式，因此适合先用设计文档把边界定清。

## Goals / Non-Goals

**Goals:**
- 将“非终态 agent 文本”和“真正的 reasoning/tool/command 过程”拆成不同语义。
- 让 canonical chat replay 可以在 plain 模式下把 agent 文本直接作为聊天内容消费，而不是依赖 promoted/final 补救。
- 为 E2E 与主 Run 观测 UI 增加默认 plain 模式，并允许用户切换回传统气泡模式。
- 明确传统气泡模式继续保留当前“非终态 agent message 归入过程气泡”的展示语义。
- 将这次改动限制在消息语义和前端展示层，不扩张到新的引擎特判或额外协议通道。

**Non-Goals:**
- 不改变 auth、tool call、command execution、turn_complete 等既有过程事件的语义。
- 不在这次 change 中重新设计整个 FCMP/RASP 事件命名体系。
- 不要求所有旧前端立刻支持新的默认展示模式，但共享前端合同会切到新语义。

## Decisions

### 1. 为非终态 agent 文本建立独立语义，而不是继续借用 reasoning

这类文本不再以 `assistant.reasoning` / `assistant_process` 近似表达，而是拥有一个新的独立消息语义。它在 runtime、schema 和 chat replay 中都要被视为“agent message”，而不是“思考过程”。

这样做的原因是：
- 这些文本对用户可见，语义上更接近正文内容；
- 把它们继续当 reasoning，会让 thinking bubble 被迫承载大量正文；
- promoted/final 本应表达收敛边界，而不是承担“把正文从推理堆里拯救出来”的职责。

备选方案：
- 保留现有 reasoning → promoted 路径，只在前端把一部分 reasoning 换个样式展示。
  - 不采用，因为这会保留协议层语义混乱，前端仍要猜哪些 reasoning 实际上是正文。

### 2. canonical chat replay 保留统一消息源，但前端按模式决定渲染位置

新的 agent message 语义要成为 canonical chat replay 的一等输入，而不是只消费最终 `assistant.message.final`。但这不意味着所有前端模式都要把它当作正文直接展开：
- 在 `plain` 模式下，agent message 直接作为对话内容展示；
- 在传统 `bubble` 模式下，非终态 agent message 继续和 `reasoning/tool/command` 一起收纳到过程气泡中。

也就是说，chat replay / 协议层需要保留统一语义，而“它是正文还是过程区的一部分”由前端展示模式决定。

备选方案：
- 只在前端本地从 RASP/FCMP 拼出新消息类型。
  - 不采用，因为 canonical chat replay 是聊天 SSOT，前端不应重新发明派生逻辑。

### 3. 保留 promoted/final，但将其职责收窄为“收敛与终态边界”

`promoted/final` 仍然保留，因为它们表达的是“哪条消息成为最终回答”和“何时终态收敛”。但它们不再承担“从 reasoning 中提取正文”的职责。

这意味着：
- 新的 agent message 可以在回合未终态时先进入聊天时间线；
- `promoted/final` 只决定最终答案的边界、去重和稳定排序；
- 相关 dedupe 逻辑要以新的 message identity 为主，而不是继续依赖“thinking bubble 被 final 覆盖”。

### 4. 前端新增 plain 模式并设为默认，气泡模式作为可切换备选

新的默认展示模式会更接近终端 plain 风格：
- agent message 直接展示为对话内容；
- reasoning/tool/command 等真正过程语义仍保持过程视图；
- 可用显示区域更大，适合长文本 agent 输出。

同时保留气泡模式切换，确保用户仍能使用传统聊天样式。在传统气泡模式下：
- 非终态 agent message 不直接展开为正文消息；
- 它继续与 `reasoning/tool/command` 等过程语义一起，被包裹在过程气泡中；
- 最终收敛后的消息仍由最终消息边界决定。

模式切换是前端展示层能力，不改变后端协议语义。

备选方案：
- 彻底替换旧气泡模式。
  - 不采用，因为一部分用户仍偏好现有气泡阅读方式，也需要一个对比回退路径。

### 5. 主 UI 与 E2E 客户端共享同一展示模式合同

`builtin-e2e-example-client` 和 `run-observability-ui` 都要消费同一套聊天语义和模式开关，而不是一边先试验、一边继续维持旧合同。

这样做的原因是：
- 两个前端都已经依赖 canonical chat replay；
- 如果 only-E2E 先改，会再次引入前端协议分叉；
- 模式切换应是 shared UI behavior，而不是单一页面的私有逻辑。

## Risks / Trade-offs

- [Risk] 旧的 promoted/final dedupe 逻辑可能和新语义重叠，导致重复消息。 → Mitigation: 在 specs 中明确新 agent message 与 promoted/final 的身份和去重优先级。
- [Risk] 前端 plain 模式和气泡模式的切换可能出现不同步的派生视图。 → Mitigation: 模式切换只影响渲染位置与分组，不影响 chat replay 源数据和消息身份。
- [Risk] 依赖 `assistant.reasoning` 近似正文的已有测试会大面积失效。 → Mitigation: 在 runtime/schema/chat replay 规格里先明确新的合同，再整体更新断言基线。
- [Risk] “新的独立语义”如果命名不清，会再次留下长期歧义。 → Mitigation: 在 specs 中为新 kind / event name 给出规范命名和使用边界。

## Migration Plan

1. 先在 `runtime-event-command-schema`、`interactive-run-observability` 和 `interactive-job-api` 中定义新的 agent message 语义及其与 promoted/final 的关系。
2. 再更新 `canonical-chat-replay`，明确新的派生规则、消息身份合同，以及 plain/bubble 两种展示模式的消费约束。
3. 之后分别更新 `builtin-e2e-example-client` 与 `run-observability-ui`，引入默认 plain 模式和模式切换开关。
4. 最后调整测试、去重逻辑和文档，确保旧 reasoning-as-message 假设被完全移除。

## Open Questions

- 新的独立语义最终应该落在现有 `assistant.message.*` 命名空间下，还是定义为独立 `assistant.agent_message` / `assistant.message.intermediate` 一类事件名？
- plain / 气泡模式的用户选择是仅会话内生效，还是需要持久化为前端偏好？
