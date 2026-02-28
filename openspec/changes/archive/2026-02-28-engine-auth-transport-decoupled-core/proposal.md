## Why

当前鉴权实现仍主要集中在 `EngineAuthFlowManager`：
1. `oauth_proxy` 与 `cli_delegate` 的状态推进、日志写入、错误处理混在同一管理器中，开发和排障时容易混淆。
2. engine 相关逻辑与 transport 相关逻辑高度耦合，新增 engine/鉴权方式时需要修改大量分支代码。
3. 会话日志目前以“单文件命名约定”组织，不利于按 transport 维度做稳定审计与回放。

为支撑后续引擎扩展与维护，本 change 将鉴权体系重构为“transport 分离 + engine 插件化驱动”的新内核。

## What Changes

1. 新增 `auth_runtime` 分层：
   - `oauth_proxy_orchestrator`
   - `cli_delegate_orchestrator`
   - `driver_registry`
   - `session_store`
   - `log_writer`
2. 将 engine 相关鉴权逻辑迁移为 driver，实现 `(engine, provider_id, auth_method, transport)` 注册分发。
3. 新增按 transport 分组的鉴权 API；旧 `/auth/sessions*` 进入兼容层并标记 deprecated。
4. 重构日志目录为：
   - `data/engine_auth_sessions/oauth_proxy/<session_id>/...`
   - `data/engine_auth_sessions/cli_delegate/<session_id>/...`
5. `EngineAuthFlowManager` 降级为 façade，仅保留兼容路由代理与聚合查询。

## Locked Decisions

1. 迁移策略为分阶段迁移，不做一次性替换。
2. API 允许重塑，提供新的 transport 分组路由。
3. 日志按 `transport + session` 分目录。
4. 抽象采用“策略注册表 + transport orchestrator”。
5. 本 change 为新增后续重构 change，不回写已有 change。

## Scope

### In Scope

1. `oauth_proxy` 与 `cli_delegate` 状态机、编排器、日志链路的结构性分离。
2. engine 无关抽象层与 driver 注册机制。
3. 新旧接口并行（旧接口兼容一个过渡周期）。
4. UI 路由切换至新 transport 分组接口。

### Out of Scope

1. 新 provider 能力扩展（本 change 不新增 provider）。
2. `auth-status` 判定规则变更。
3. 部署模式自动切换策略。

## Success Criteria

1. `oauth_proxy` 会话状态流中不再出现 `waiting_orchestrator`。
2. `cli_delegate` 会话状态流可稳定进入 `waiting_orchestrator`。
3. 同一 engine 在不同 transport 下通过统一快照模型输出，且状态语义一致可解释。
4. 新 transport 分组 API 可用，旧接口兼容可用并返回 deprecated 标记。
5. 鉴权日志目录与文件类型严格按 transport 分离。
