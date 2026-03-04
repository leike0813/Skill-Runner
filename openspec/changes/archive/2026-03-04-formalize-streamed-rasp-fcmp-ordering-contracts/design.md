## Context

当前 runtime 已经同时存在多条潜在排序路径：

- parser 增量产出的 live emission 顺序
- orchestration 直接发布状态事件的顺序
- audit mirror 的写盘顺序
- batch rebuild / backfill 的重建顺序
- SSE 与 `/events/history` 的消费顺序
- terminal summary / result projection 的暴露顺序

这些路径之间还没有被同一个合同统一起来。与此同时，FCMP conversation lifecycle 还保留了两套表达方式：

- `conversation.state.changed`
- `conversation.started/completed/failed`

它们在生命周期表达上高度重叠，导致：

- active run 的源事件与 UI/summary/result projection 之间可能出现投影超前
- auth 引导和 challenge/link 等事件可能被反序暴露
- live SSE 与 history replay 可能看到不同的相对顺序
- audit/backfill 有机会污染 active run 的当前顺序
- terminal lifecycle 需要额外维护 paired-event 规则

这个 change 的作用不是立刻把所有实现修完，而是先把“谁决定顺序、谁只能镜像、谁只能投影、谁不能重排”定义为 SSOT，并收敛 FCMP lifecycle 事件模型。后续实现必须服从这套合同。

## Goals / Non-Goals

**Goals:**

- 定义 streamed RASP 的 canonical 顺序来源
- 定义 parser-originated FCMP 与 orchestration-originated FCMP 的统一排序模型
- 定义 auth、waiting/reply、terminal/result projection 的因果先后约束
- 定义 live SSE 与 `/events/history` 的一致性合同
- 定义 audit mirror 与 batch backfill 的职责下界，禁止它们重排 active truth
- 引入 `RuntimeEventOrderingGate` / buffer 的实现骨架，让顺序仲裁有明确边界
- 收敛 FCMP conversation lifecycle，只保留 `conversation.state.changed`
- 让这些规则能被 invariants、specs、schema 和测试直接守护

**Non-Goals:**

- 不在本 change 中重写整个 state machine
- 不在本 change 中把所有现存前端现象逐个修掉
- 不在本 change 中改变 `.state/state.json` 作为 run status 真相源的地位
- 不在本 change 中重做 auth 业务设计本身
- 不在本 change 中引入新的前端业务协议替代 FCMP

## Decisions

### Decision 1: 活跃 runtime event 的 canonical order 由 publish order 决定

规则：

- active run 中，FCMP/RASP 的 canonical 顺序只能由 publish 时刻决定
- audit mirror、history materialization、batch rebuild 都不得决定 active order
- mirror 和 backfill 只能补历史，不能改写已经发布的顺序

这样可以把“当前真相”和“历史镜像”彻底分层，避免文件时延重新定义语义顺序。

### Decision 2: 必须新增独立的机器可读顺序合同文件

新增：

- `docs/contracts/runtime_event_ordering_contract.yaml`

它与 `session_fcmp_invariants.yaml` 分工如下：

- `session_fcmp_invariants.yaml`
  - 继续负责状态机、状态迁移、FCMP 映射和状态不变量
- `runtime_event_ordering_contract.yaml`
  - 专门负责：
    - event kinds
    - precedence rules
    - gating rules
    - projection rules
    - replay rules
    - buffer policies
    - lifecycle normalization rules

### Decision 3: 引入顺序仲裁层，而不是普通 FIFO 队列

新增内部组件：

- `RuntimeEventOrderingGate`

以及配套内部概念：

- `RuntimeEventCandidate`
- `OrderingPrerequisite`
- `OrderingDecision`
- `ProjectionGateState`
- `FcmpOrderingBuffer`
- `RaspOrderingBuffer`

规则：

- parser 不得直接 publish FCMP/RASP
- orchestration 不得直接 publish lifecycle FCMP
- projection 不得直接对外暴露 terminal summary/result
- 所有这些都先产出 candidate，再由 gate/buffer 判定是否可发布

这里的“缓冲区”不是为了简单排序，而是为了保证“只有当前置条件满足时才能发布”。

### Decision 4: FCMP 与 RASP 采用双流保序模型

规则：

- FCMP 保持独立的 `fcmp_seq`
- RASP 保持独立的 `rasp_seq`
- 二者不共用同一个整数 seq 空间
- 二者必须通过 `publish_id` 与必要时的 `caused_by.publish_id` 建立稳定关联

原因：

- FCMP 面向前端业务流，要求 run 级 publish 顺序
- RASP 面向审计与证据回溯，更适合保持 attempt 级 parser emission 语义顺序

### Decision 5: RASP 的 canonical order 定义为 live parser emission order

规则：

- 同一个 attempt 内，RASP 的 canonical 顺序由 `LiveStreamParserSession.feed()/finish()` 的 emission 顺序决定
- audit mirror 必须按已发布的 `rasp_seq` 追加写入
- replay/backfill 读取时只能按 `rasp_seq` 恢复，不得按文件时间或到达顺序猜测

RASP 的 buffer/gate 主要做：

- 固化 parser emission 顺序
- 等待必要 metadata 补齐
- 保护 mirror/replay 不破坏顺序

### Decision 6: FCMP lifecycle 事件收敛为单轨

协议收敛规则：

- 删除 `conversation.started`
- 删除 `conversation.completed`
- 删除 `conversation.failed`
- 仅保留 `conversation.state.changed`

这样做的原因：

- `conversation.started` 已基本被 `conversation.state.changed(queued->running)` 取代
- `conversation.completed/failed` 与 terminal `conversation.state.changed` 生命周期表达重复
- 保留双轨只会让顺序 gate 继续维护 paired terminal event 复杂度

### Decision 7: terminal 语义折叠进 `conversation.state.changed.data.terminal`

对 terminal state 增加稳定字段：

- `terminal.status`
- `terminal.error`
- `terminal.diagnostics`

规则：

- 仅 `to in {succeeded, failed, canceled}` 时允许出现 `terminal`
- 非 terminal 状态不得携带 `terminal`
- `terminal.status` 必须等于 `to`

这样取代原先 `conversation.completed` / `conversation.failed` 的终态语义承载。

### Decision 8: 必须定义关键业务链路的因果先后约束

#### Auth

- `auth.method.selection.required` 必须先于任何依赖选择结果的 `auth.challenge.updated`
- 若 challenge 要求 callback URL，则操作说明必须先可见，再可见 challenge/link

#### Waiting / Reply

- `interaction.prompted` 或等价 waiting 语义事件必须先于 `waiting_user` 的稳定可见
- `interaction.reply.accepted` 不得早于对应 interaction 实际存在
- resumed attempt 的 `running` 不得早于 reply accepted 已发布

#### Terminal / Projection

- 成功路径下，若需要最终回答，则 `assistant.message.final` 必须先于 terminal `conversation.state.changed(... -> succeeded)`
- terminal projection 不得早于 canonical terminal lifecycle event 前置条件满足
- run 处于 `waiting_user` / `waiting_auth` 时，禁止暴露空 terminal result/summary

### Decision 9: SSE 与 `/events/history` 必须共享同一排序模型

规则：

- live SSE 与 `/events/history` 必须遵守同一 canonical publish order
- active / recent runs 优先 memory-first replay
- older/restarted runs 允许 audit fallback
- fallback 允许缺历史，不允许重排历史

### Decision 10: batch rebuild 明确降级为 parity/backfill only

保留 `build_rasp_events(...)` 与 `build_fcmp_events(...)`，但职责改为：

- audit fallback
- parity tests
- 旧 run / 进程重启后的冷回放

禁止：

- 作为 active run live SSE 的前置
- 覆盖已经发布过的 live order

## Risks / Trade-offs

- [风险] 引入 gate/buffer 后实现复杂度上升  
  → 先在本 change 中定义明确的合同与类型骨架，再逐步把 live pipeline 接入 gate，避免一口气重构穿整个 runtime。

- [风险] 收敛 lifecycle 事件会影响 UI、schema、fixtures 和测试样例  
  → 同步更新 schema、template 消费逻辑和关键测试，避免保留双轨兼容分支。

- [风险] 现有 live 实现与新合同不一致，后续收敛成本较高  
  → 在 tasks 中先安排 invariants、docs、specs、schema 和测试矩阵，再做实现收敛，避免继续叠热修。

- [风险] batch backfill 与 live publish 的 parity 可能不稳定  
  → 把 parity 作为专门测试维度，而不是让 backfill 继续参与 active order 计算。

## Migration Plan

1. 更新 change artifact，使其覆盖顺序合同 + lifecycle 收敛合同。
2. 新增 `runtime_event_ordering_contract.yaml`，并同步更新 invariants 与文档。
3. 收敛 FCMP lifecycle 事件、schema、factory 和 protocol 生成逻辑。
4. 更新 UI/history/replay 消费路径，使其只依赖 canonical lifecycle FCMP。
5. 增加 ordering contract、lifecycle normalization、live/history consistency 与场景回归测试。
6. 后续再逐步让 live publish、observability、orchestration、parser 实现统一收敛到 gate 驱动。

## Open Questions

- 无。当前 change 已锁定为“顺序合同 + 生命周期事件收敛合同”，不再额外引入产品层决策。
