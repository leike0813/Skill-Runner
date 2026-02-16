## Context

现有 Jobs API 只有创建、上传、查询、下载等只读或一次性动作，缺失“执行暂停后继续”的协议层。  
如果不先定义 API 合同，`job_orchestrator` 与 adapter 层会出现状态和载荷不一致的问题。

## Goals

1. 在不破坏现有 `auto` 行为的前提下引入 `interactive` 模式。
2. 定义可稳定演进的交互 API 协议（pending/reply）。
3. 保证调用侧可通过 request_id 完成“查询待决问题 + 提交答复 + 等待继续执行”闭环。
4. 明确错误码和并发提交行为，避免重复回复导致状态错乱。

## Non-Goals

1. 本 change 不改 UI 页面交互能力。
2. 本 change 不实现 orchestrator 内部状态机细节（由后续 change 实现）。
3. 本 change 不定义 token 级流式输出，仅做“回合级”交互。

## Design

### 1) 运行模式字段

- 推荐落位：`runtime_options.execution_mode`。
- 取值：`auto`（默认）或 `interactive`。
- 校验：通过 `options_policy` allowlist 显式放行，未知值返回 400。

### 2) 交互查询接口

`GET /v1/jobs/{request_id}/interaction/pending`

- 返回示例：
  - `status=waiting_user` 且存在待答问题：返回 `pending` 对象。
  - 无待答问题：`pending: null`，并返回当前 run 状态。
- `pending` 最小字段：
  - `interaction_id: int`
  - `kind: decision | clarification | confirmation`
  - `prompt: string`
  - `options: [{label, value}]`（可选）
  - `required_fields: [string]`（可选）
  - `context: object`（可选摘要）

### 3) 交互回复接口

`POST /v1/jobs/{request_id}/interaction/reply`

- 请求字段：
  - `interaction_id`（必填）
  - `response`（object，允许多种结构）
  - `idempotency_key`（可选）
- 前置条件：
  - run 必须处于 `waiting_user`；
  - `interaction_id` 必须等于当前待答 id。
- 成功语义：
  - 记录回复并触发恢复执行（异步）；
  - 返回 `accepted=true` 与当前状态（通常转为 `queued/running`）。

### 4) 幂等与冲突语义

- 相同 `idempotency_key` + 相同请求体可安全重放，返回同一 accepted 结果。
- `interaction_id` 不匹配或已消费：返回 409，提示“stale interaction”。
- run 已终态时回复：返回 409。

### 5) 与缓存关系

- `interactive` 模式下跳过缓存命中逻辑；
- 不写入成功缓存条目，避免后续请求被错误复用。

## Risks & Mitigations

1. **风险：回复载荷结构发散**
   - 缓解：先统一为 `response: object`，并在 pending 中给出 `required_fields` 和 `options`。
2. **风险：重复提交导致并发恢复**
   - 缓解：强制 `interaction_id` 校验 + 可选 `idempotency_key` 去重。
3. **风险：兼容性回归**
   - 缓解：默认 `auto`，并补充对旧请求体的单测回归。
