## 1. OpenSpec

- [x] 1.1 完成 proposal/design/tasks 与 3 份 delta spec
- [x] 1.2 运行 `openspec validate engine-auth-transport-decoupled-core --type change`

## 2. Runtime Core

- [x] 2.1 新增 `auth_runtime` 目录与基础模块（orchestrators/drivers/store/log_writer）
- [x] 2.2 实现 `AuthDriverRegistry`
- [x] 2.3 实现 `OAuthProxyOrchestrator`
- [x] 2.4 实现 `CliDelegateOrchestrator`
- [x] 2.5 实现 `SessionStore` 与统一快照转换
- [x] 2.6 实现 transport 分目录日志写入

## 3. Migration

- [x] 3.1 将 `oauth_proxy` 迁移至新 orchestrator（codex + opencode/openai）
- [x] 3.2 将 `cli_delegate` 迁移至新 orchestrator（codex/opencode/gemini/iflow）
- [x] 3.3 `EngineAuthFlowManager` 降级为 façade 并保留兼容层

## 4. API + UI

- [x] 4.1 `server/models.py` 新增 V2 模型（start/snapshot/input）
- [x] 4.2 `server/routers/engines.py` 新增 transport 分组 API
- [x] 4.3 `server/routers/ui.py` 新增 transport 分组 API
- [x] 4.4 旧 `/auth/sessions*` 接口接入兼容层并标 deprecated
- [x] 4.5 `server/assets/templates/ui/engines.html` 切换到 V2 接口调用

## 5. Tests

- [x] 5.1 新增 `test_oauth_proxy_orchestrator.py`
- [x] 5.2 新增 `test_cli_delegate_orchestrator.py`
- [x] 5.3 新增 `test_auth_driver_registry.py`
- [x] 5.4 新增 `test_auth_log_writer.py`
- [x] 5.5 更新 `test_v1_routes.py` 与 `test_ui_routes.py`
- [x] 5.6 回归 `engine interaction gate` 与现有 gemini/iflow/opencode 非 openai 链路

## 6. Docs

- [x] 6.1 更新 `docs/api_reference.md`
- [x] 6.2 更新 `docs/e2e_example_client_ui_reference.md`
- [x] 6.3 更新 `docs/containerization.md`
