## 1. OpenSpec

- [x] 1.1 新建 `engine-auth-runtime-modularization-phase1` 四工件与 delta specs
- [x] 1.2 运行 `openspec validate engine-auth-runtime-modularization-phase1 --type change`

## 2. 已完成基线（实现先行补录）

- [x] 2.1 新增 `server/runtime/auth/session_start_planner.py`
- [x] 2.2 新增 `server/runtime/auth/session_refresher.py`
- [x] 2.3 新增 `server/runtime/auth/session_input_handler.py`
- [x] 2.4 新增 `server/runtime/auth/session_callback_completer.py`
- [x] 2.5 `EngineAuthFlowManager` 已接入 input/callback/refresher/planner 委托
- [x] 2.6 已完成回归：`test_engine_auth_flow_manager.py`、`test_v1_routes.py`、`test_ui_routes.py`

## 3. 本次核心实现

- [x] 3.1 新增 `server/runtime/auth/session_starter.py`
- [x] 3.2 `EngineAuthFlowManager.start_session` 仅保留 façade 编排并委托 `session_starter`
- [x] 3.3 清理 manager 中多余 start 分支残留（含无效 import/常量）
- [x] 3.4 在 `docs/developer/auth_runtime_driver_guide.md` 补充 `planner->starter->refresher/input/callback` 完整调用链

## 4. 测试与验证

- [x] 4.1 新增 `tests/unit/test_auth_session_starter.py`
- [x] 4.2 更新 `tests/unit/test_engine_auth_flow_manager.py`（覆盖 façade 委托路径）
- [x] 4.3 回归测试：
  - `tests/unit/test_engine_auth_flow_manager.py`
  - `tests/unit/test_oauth_proxy_orchestrator.py`
  - `tests/unit/test_cli_delegate_orchestrator.py`
  - `tests/unit/test_v1_routes.py`
  - `tests/unit/test_ui_routes.py`
- [x] 4.4 mypy 覆盖：
  - `server/runtime/auth/session_starter.py`
  - `server/services/engine_auth_flow_manager.py`
