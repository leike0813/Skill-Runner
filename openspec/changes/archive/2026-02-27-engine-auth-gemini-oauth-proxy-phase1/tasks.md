## 1. OpenSpec Artifacts

- [x] 1.1 完成 proposal（明确零 CLI、双回调、存储边界）。
- [x] 1.2 完成 design（状态机、listener、token exchange、写盘策略）。
- [x] 1.3 完成 delta specs：
  - management-api-surface
  - ui-engine-management
  - engine-auth-observability
- [x] 1.4 运行 `openspec validate engine-auth-gemini-oauth-proxy-phase1 --type change` 并通过。

## 2. Backend Implementation

- [x] 2.1 新增 `gemini_oauth_proxy_flow.py`（PKCE/state/auth_url/exchange/write）。
- [x] 2.2 新增 `gemini_local_callback_server.py`（本地回调监听）。
- [x] 2.3 扩展 `engine_auth_flow_manager.py`：
  - 注册 gemini oauth_proxy driver
  - start/refresh/input/finalize/state 索引接入
  - 状态机保持 oauth_proxy 语义
- [x] 2.4 扩展 `oauth_proxy_orchestrator.py` 允许 gemini 映射。
- [x] 2.5 保持 Gemini `cli_delegate` 行为不变。

## 3. UI / API Integration

- [x] 3.1 管理页新增 Gemini OAuth 代理按钮。
- [x] 3.2 输入提示按 transport 区分（oauth_proxy vs cli_delegate）。
- [x] 3.3 验证 grouped 路由行为不变，仅新增有效组合。

## 4. Tests & Validation

- [x] 4.1 新增 `test_gemini_oauth_proxy_flow.py`。
- [x] 4.2 新增 `test_gemini_local_callback_server.py`。
- [x] 4.3 更新 `test_engine_auth_flow_manager.py`（gemini oauth_proxy 路径）。
- [x] 4.4 更新 `test_oauth_proxy_orchestrator.py`。
- [x] 4.5 更新 `test_ui_routes.py`（按钮与页面行为）。
- [x] 4.6 执行改动相关 pytest。
- [x] 4.7 执行改动文件集 mypy。

## 5. Docs

- [x] 5.1 更新 `docs/api_reference.md`（Gemini oauth_proxy 组合与 fallback）。
- [x] 5.2 更新 `docs/e2e_example_client_ui_reference.md`（新按钮与交互）。
- [x] 5.3 更新 `docs/containerization.md`（本地回调与手工兜底说明）。
