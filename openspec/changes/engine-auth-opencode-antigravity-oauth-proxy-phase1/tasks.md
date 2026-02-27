## 1. OpenSpec Artifacts

- [x] 1.1 完成 proposal（明确零 CLI、双回调、单账号覆盖）。
- [x] 1.2 完成 design（状态机、listener、写盘与审计）。
- [x] 1.3 完成 delta specs：
  - management-api-surface
  - ui-engine-management
  - engine-auth-observability
- [x] 1.4 运行 `openspec validate engine-auth-opencode-antigravity-oauth-proxy-phase1 --type change` 并通过。

## 2. Backend Implementation

- [x] 2.1 新增 `opencode_google_antigravity_oauth_proxy_flow.py`（PKCE/state/auth_url/exchange）。
- [x] 2.2 新增 `antigravity_local_callback_server.py`（51121 回调监听）。
- [x] 2.3 扩展 `opencode_auth_store.py`（single-account v4 覆盖写入）。
- [x] 2.4 扩展 `engine_auth_flow_manager.py`：
  - 注册 `opencode+google+oauth_proxy+browser-oauth`
  - start/refresh/input/callback/finalize 全链路接入
  - 审计字段回写
- [x] 2.5 保持现有 `cli_delegate` Google 路径行为不变。

## 3. UI / API Integration

- [x] 3.1 管理页新增 OpenCode Google OAuth 代理按钮。
- [x] 3.2 确认按钮发起 payload：
  - `engine=opencode`
  - `transport=oauth_proxy`
  - `provider_id=google`
  - `auth_method=browser-oauth`
- [x] 3.3 手工输入 fallback 继续走 `/input(kind=text)`。

## 4. Tests & Validation

- [x] 4.1 新增 `test_opencode_google_antigravity_oauth_proxy_flow.py`。
- [x] 4.2 新增 `test_antigravity_local_callback_server.py`。
- [x] 4.3 更新 `test_engine_auth_flow_manager.py`（新组合 + callback + fallback）。
- [x] 4.4 更新 `test_v1_routes.py` / `test_ui_routes.py`（组合放行与 UI 行为）。
- [x] 4.5 执行改动文件相关 pytest。
- [x] 4.6 执行改动文件集 mypy。

## 5. Docs

- [x] 5.1 更新 `docs/api_reference.md`（新有效组合与 fallback 说明）。
- [x] 5.2 更新 `docs/e2e_example_client_ui_reference.md`（按钮与交互）。
- [x] 5.3 更新 `docs/containerization.md`（51121 本地监听与 fallback 说明）。
