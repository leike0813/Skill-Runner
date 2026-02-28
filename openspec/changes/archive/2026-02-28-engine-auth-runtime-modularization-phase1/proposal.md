## Why

近期 auth 侧发生了多轮拆分（planner/refresher/input/callback completer），实现已经前进，但现有 change 记录未完整覆盖，产生了 “实现先行、spec 滞后” 偏移。

此外，`EngineAuthFlowManager.start_session` 仍保留大块 engine-specific 启动分支，和 phase2“façade 化”目标不一致。

## What Changes

1. 新增 auth 专项增量 change，作为 `engine-auth-adapter-verticalization-core-phase2` 的后续补强，不回退既有实现。
2. 固化 auth runtime 服务分层：`session_start_planner`、`session_starter`、`session_refresher`、`session_input_handler`、`session_callback_completer`。
3. 将 `start_session` 剩余启动分支从 manager 下沉到 `session_starter`，使 manager 仅保留 façade 职责。
4. 维护 engine-specific 边界：实现仅在 `server/engines/<engine>/auth/*`。
5. 对外 API 保持兼容，不新增或删除 `/v1`、`/ui` auth 端点。

## Scope

### In Scope

1. OpenSpec 与实现对齐（记录已完成基线并补齐任务状态）。
2. auth runtime 结构化拆分与 manager 瘦身（聚焦 start 路径）。
3. 测试补齐：新增 starter 单测，回归 manager/routes/orchestrator 关键用例。
4. 开发者文档补强（调用链、扩展点、最小接入步骤）。

### Out of Scope

1. 不新增 provider、不新增 transport、不新增公开端点。
2. 不变更鉴权业务语义与状态机定义。
3. 不进行 adapter 新功能开发。

## Success Criteria

1. `EngineAuthFlowManager` 不再承载 engine-specific 启动大分支。
2. `session_starter` 成为 start 业务承接点，且行为与现状一致。
3. OpenSpec tasks 中已实现基线明确勾选并可追溯文件落点。
4. 关键单测与回归测试通过，`openspec validate` 通过。
