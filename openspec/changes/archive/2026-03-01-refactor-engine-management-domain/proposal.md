## Why

`server/services/orchestration` 当前同时承载 run 编排与 engine 管理职责。  
`agent_cli_manager`、`engine_auth_flow_manager`、`engine_upgrade_manager`、`model_registry`、`runtime_profile` 等 engine-domain 组件散落在 orchestration 目录，导致边界语义模糊、依赖面扩大、维护复杂度上升。

## What Changes

- 新增 `server/services/engine_management` 域包。
- 将 orchestration 下 11 个 engine 管理模块整体迁移到新包。
- 一次性切换全仓 import 到新路径，不保留 orchestration 兼容 re-export 壳。
- 保持类名、函数名、单例名与对外行为不变（仅路径重构）。

## Capabilities

### Added Capabilities
- `engine-management-domain-boundary`:
  - engine 管理模块的目录归属与责任边界收敛到 `services/engine_management`。
  - 迁移后全仓依赖统一指向新包，不再继续耦合到 orchestration。

## Impact

- Affected code:
  - `server/services/engine_management/*`（new）
  - `server/services/orchestration/*`（import 更新与旧文件删除）
  - `server/routers/*`, `server/services/skill/*`, `server/services/ui/*`, `server/engines/*`
  - `tests/unit/*`, `tests/engine_integration/*`, `tests/e2e/*`
- Affected docs:
  - `docs/core_components.md`
  - `docs/project_structure.md`
- Public API:
  - HTTP API: 无变化
  - Runtime schema/invariants: 无变化
