## 1. OpenSpec Artifacts

- [ ] 1.1 完成 proposal/design/tasks 与 3 个 delta spec。
- [ ] 1.2 运行 `openspec validate engine-auth-iflow-oauth-proxy-phase1 --type change` 并通过。

## 2. Backend Implementation

- [ ] 2.1 新增 `iflow_oauth_proxy_flow.py`（authorize/token/user-info/写盘）。
- [ ] 2.2 新增 `iflow_local_callback_server.py`（本地回调监听）。
- [ ] 2.3 扩展 `engine_auth_flow_manager.py`：
  - 注册 iflow oauth_proxy driver
  - start/refresh/input/callback/finalize 接入
  - state 索引与 listener 生命周期管理
- [ ] 2.4 扩展 `oauth_proxy_orchestrator.py` 放行 iflow。
- [ ] 2.5 保持 `iflow cli_delegate` 行为不变。

## 3. UI / API Integration

- [ ] 3.1 管理页新增 iFlow OAuth 代理双入口按钮。
- [ ] 3.2 输入提示与输入框行为符合 iflow 双模式语义。
- [ ] 3.3 grouped 路由保持兼容，不新增端点。

## 4. Tests & Validation

- [ ] 4.1 新增 `test_iflow_oauth_proxy_flow.py`。
- [ ] 4.2 新增 `test_iflow_local_callback_server.py`。
- [ ] 4.3 更新 `test_engine_auth_flow_manager.py`（iflow oauth_proxy）。
- [ ] 4.4 更新 `test_oauth_proxy_orchestrator.py`（iflow 放行）。
- [ ] 4.5 更新 `test_ui_routes.py` / `test_v1_routes.py`（UI 按钮与接口组合）。
- [ ] 4.6 运行改动相关 pytest。
- [ ] 4.7 运行改动文件集 mypy。

## 5. Docs

- [ ] 5.1 更新 `docs/api_reference.md`（iflow oauth_proxy 双模式）。
- [ ] 5.2 更新 `docs/e2e_example_client_ui_reference.md`（管理页测试矩阵）。
- [ ] 5.3 更新 `docs/containerization.md`（iflow callback/fallback 说明）。
