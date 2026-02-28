## 1. OpenSpec

- [x] 1.1 新建 `engine-auth-runtime-modularization-phase2` 四工件与 delta specs
- [x] 1.2 运行 `openspec validate engine-auth-runtime-modularization-phase2 --type change`

## 2. Runtime/Core 去 engine 化

- [x] 2.1 `AuthSessionStartPlanner` 改为通过 engine handler `plan_start` 委托
- [x] 2.2 `AuthSessionStarter` 改为通过 engine handler `start_session_locked` 委托
- [x] 2.3 `AuthSessionRefresher` 改为通过 engine handler `refresh_session_locked` 委托
- [x] 2.4 `AuthSessionInputHandler` 改为通过 engine handler `handle_input` 委托
- [x] 2.5 `AuthSessionCallbackCompleter` 改为通过 engine handler `complete_callback` 委托
- [x] 2.6 callback 完成链路统一为 `complete_callback(channel, state, code, error)`，移除 runtime 层按引擎命名入口
- [x] 2.7 合并 session 组件到 `server/runtime/auth/session_lifecycle.py`，移除分散的五个 `session_*` 模块文件
- [x] 2.8 合并 callback 相关模块到 `server/runtime/auth/callbacks.py`，移除 `callback_router/state_store/listener_registry` 三文件

## 3. Manager 收口（façade）

- [x] 3.1 `EngineAuthFlowManager` 接线 engine handler registry
- [x] 3.2 manager `start_session` 保持 façade 编排（plan -> start）
- [x] 3.3 manager 终态清理改为 handler hook（`on_session_finalizing`）
- [x] 3.4 manager 终止策略改为 handler hook（`terminate_session`）
- [x] 3.5 trust 注入策略改为 handler hook（`requires_parent_trust_bootstrap`）

## 4. Engine-specific 下沉

- [x] 4.1 `codex` runtime handler 补齐 finalize/terminate/trust hooks
- [x] 4.2 `gemini` runtime handler 补齐 finalize/terminate/trust hooks
- [x] 4.3 `iflow` runtime handler 补齐 finalize/terminate/trust hooks
- [x] 4.4 `opencode` runtime handler 补齐 finalize/terminate/trust hooks（含 antigravity rollback 下沉）
- [x] 4.5 CodeX/OpenCode 共用 OpenAI 协议入口迁移到 `server/engines/common/openai_auth/*`
- [x] 4.6 清理 `server/runtime/auth/providers/*`，避免 runtime 承载共享协议实现

## 5. 质量门禁

- [x] 5.1 新增 `tests/unit/test_runtime_auth_no_engine_coupling.py`
- [x] 5.2 关键回归通过：
  - `tests/unit/test_engine_auth_flow_manager.py`
  - `tests/unit/test_auth_session_starter.py`
  - `tests/unit/test_oauth_proxy_orchestrator.py`
  - `tests/unit/test_cli_delegate_orchestrator.py`
  - `tests/unit/test_v1_routes.py`
  - `tests/unit/test_ui_routes.py`
- [x] 5.3 mypy 通过（变更文件集）

## 6. 文档

- [x] 6.1 更新 `docs/developer/auth_runtime_driver_guide.md`（runtime 零 engine-specific 约束）
- [x] 6.2 更新 `docs/developer/engine_onboarding_example.md`（auth driver 接入顺序）
