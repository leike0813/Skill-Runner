## Context

现有可观测逻辑主要区分 `queued/running/succeeded/failed/canceled`，  
并默认 `queued/running` 需要继续轮询日志。交互模式引入后，`waiting_user` 语义不同：非终态，但无执行进程。

## Goals

1. 让 API 调用方能明确识别并处理 `waiting_user`。
2. 降低等待阶段的无效日志轮询。
3. 形成覆盖交互生命周期的可回归测试体系。
4. 保证文档、测试、实现三者一致。

## Non-Goals

1. 不实现 WebSocket 推送。
2. 不新增 UI 交互页面。
3. 不在本 change 调整引擎执行策略本身。

## Prerequisite

- `interactive-25-api-sse-log-streaming` 已定义并落地 SSE 事件流接口。
- `interactive-27-unified-management-api-surface` 已定义并落地通用管理 API 语义。
- `interactive-28-web-client-management-api-migration` 已完成内建客户端迁移与旧 UI 接口弃用策略落地。
- `interactive-26-job-termination-api-and-frontend-control` 已定义并落地取消终态语义。
- `interactive-29-decision-policy-and-auto-continue-switch` 已定义 strict 开关与自动决策分流语义。
- 本 change 不重复定义 SSE 事件协议，仅定义其在交互生命周期中的观测语义与测试要求。

## Design

### 1) 状态与轮询语义

- `waiting_user` 作为非终态保留在状态接口；
- `run_observability` 中：
  - `poll_logs` 对 `running/queued` 为 `true`；
  - 对 `waiting_user` 为 `false`。

### 2) 可观测字段

在状态响应中补充：
- `pending_interaction_id`（可空）
- `interaction_count`（历史问答计数，可选）

用于客户端判定“是否需要进入答复流程”。

### 3) 测试策略

新增最小交互 fixture（可由假 adapter 驱动）：
- Case A：一次 ask_user 后成功；
- Case B：两次 ask_user 后失败；
- Case C：auto 模式无变化。

### 4) 文档同步

更新 API 文档中 Jobs 章节：
- 增加 interactive 流程时序；
- 明确 `waiting_user` 的轮询建议；
- 明确 reply 的冲突码（409）处理建议。

## Risks & Mitigations

1. **风险：客户端误把 waiting_user 当终态**
   - 缓解：文档与响应字段双重提示，并在 e2e 中验证推荐轮询策略。
2. **风险：日志轮询策略变更引入回归**
   - 缓解：补充 `test_run_observability` 断言 `poll_logs/poll` 逻辑。
3. **风险：测试复杂度上升**
   - 缓解：以 fake adapter 驱动核心生命周期，减少对真实 CLI 的依赖。
