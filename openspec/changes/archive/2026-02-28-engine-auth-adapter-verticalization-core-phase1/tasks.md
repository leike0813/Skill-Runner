## 1. OpenSpec

- [x] 1.1 新建 change 四工件与 4 份 delta spec
- [x] 1.2 运行 `openspec validate engine-auth-adapter-verticalization-core-phase1 --type change`

## 2. Runtime/Auth Core

- [x] 2.1 新增 `server/runtime/auth/contracts.py`
- [x] 2.2 新增 `server/runtime/auth/driver_registry.py`
- [x] 2.3 transport orchestrator 去除 engine-specific 分支（改 capability resolver）
- [x] 2.4 `EngineAuthFlowManager` 保持 façade 语义并接入新 registry

## 3. Runtime/Adapter Core

- [x] 3.1 新增 `server/runtime/adapter/contracts.py`
- [x] 3.2 新增 `server/runtime/adapter/base_execution_adapter.py`

## 4. Engine Verticalization

- [x] 4.1 新建 `server/engines/{codex,gemini,iflow,opencode}/adapter/*` 并接入旧 adapter 桥接
- [x] 4.2 新建 `server/engines/{codex,gemini,iflow,opencode}/auth/*` 并接入旧 auth flow 桥接
- [x] 4.3 `server/services/engine_adapter_registry.py` 切换到引擎包入口

## 5. Tests & Docs

- [x] 5.1 新增 `test_engine_auth_driver_contracts.py`
- [x] 5.2 新增 `test_engine_auth_driver_matrix_registration.py`
- [x] 5.3 新增 `test_adapter_component_contracts.py`
- [x] 5.4 新增 `test_engine_package_bootstrap.py`
- [x] 5.5 回归 `test_engine_auth_flow_manager.py`、`test_oauth_proxy_orchestrator.py`、`test_cli_delegate_orchestrator.py`
- [x] 5.6 回归 `test_engine_adapter_registry.py` 与四引擎 adapter 相关测试
- [x] 5.7 变更文件集执行 mypy
