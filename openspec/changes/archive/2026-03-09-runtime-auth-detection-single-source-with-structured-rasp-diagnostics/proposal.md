## Why

当前 auth 判定链路已向 parser 信号收敛，但仍存在两类收尾缺口：

1. RASP 诊断表达仍偏弱，主要靠 `code`，缺少结构化 auth 证据快照。
2. SSOT 与守卫未完全固化，后续容易出现“声明源漂移 / 二次判定回流”。

本次 change 目标是把 runtime auth detection 收口为可维护的单源模型，并在不改变 RASP 事件外壳的前提下，补齐结构化诊断能力。

## What Changes

- 维持 parser 单次判定：声明证据 -> parser 产 `auth_signal`。
- 生命周期仅消费 `auth_signal_snapshot`，不再做二次 detect。
- RASP `diagnostic.warning` 增量扩展 `data.auth_signal`（结构化）。
- 明确 `confidence` 仅 `high|low`：
  - engine-specific evidence 默认 `high`
  - common fallback evidence 固定 `low`
- 新增 SSOT/守卫约束，禁止再次引入双源与硬编码样式。

## Impact

- 外部 HTTP API：无变化。
- FCMP/RASP 事件类型：无变化（仅 `diagnostic.warning.data` 扩展字段）。
- 运行行为：
  - `high` 可驱动 `waiting_auth`
  - `low` 仅诊断，不进入 `waiting_auth`
