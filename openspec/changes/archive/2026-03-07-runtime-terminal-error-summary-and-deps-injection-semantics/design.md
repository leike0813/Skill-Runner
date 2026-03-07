## Context

terminal 事件当前存在两类来源：
- orchestrator append + live translate
- history 重放 `build_fcmp_events`

两条路径对 terminal 错误摘要处理不一致，导致“live 看不到详细失败原因 / history 看不到详细失败原因”问题反复出现。  

同时，`runtime.dependencies` 仅停留在 manifest 数据结构，未进入 adapter 执行决策。

## Decisions

### 1) terminal 错误摘要 contract

- `lifecycle.run.terminal.data` 扩展可选字段：
  - `code: string`
  - `message: string`（长度受控摘要）
- `failed/canceled` 时优先填充上述字段。
- FCMP terminal `conversation.state.changed.data.terminal.error` 优先消费这组字段。

### 2) error.run.failed 映射收敛

- `error.run.failed` 保留为审计事件。
- FCMP 翻译从“直接生成 terminal state change”收敛为 `diagnostic.warning`，避免与 `lifecycle.run.terminal` 重复发布 terminal state。

### 3) runtime.dependencies 执行语义

- adapter 在真实 agent 命令前执行 `uv` 注入探测。
- 探测成功才启用 `uv run --with ... -- ...` 包装。
- 探测失败采用 best-effort fallback：
  - 发布 `RUNTIME_DEPENDENCIES_INJECTION_FAILED` warning
  - 继续执行原始 agent 命令

## Non-Goals

- 不引入 strict/fail-fast 开关（本次固定 best-effort）。  
- 不改变 run statechart、FCMP 事件类型集合或外部 API 路径。
