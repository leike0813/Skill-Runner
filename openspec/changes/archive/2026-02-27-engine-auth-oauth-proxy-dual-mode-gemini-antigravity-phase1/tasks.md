## 1. OpenSpec Artifacts

- [x] 1.1 完成 proposal（旧值废弃 + 双模式补齐）。
- [x] 1.2 完成 design（矩阵、强分离、失败语义）。
- [x] 1.3 完成 delta specs：
  - management-api-surface
  - ui-engine-management
  - engine-auth-observability
- [x] 1.4 运行 `openspec validate engine-auth-oauth-proxy-dual-mode-gemini-antigravity-phase1 --type change` 并通过。

## 2. Backend

- [x] 2.1 `engine_auth_flow_manager` 统一新 `auth_method` 并移除旧值兼容。
- [x] 2.2 `oauth_proxy`：Gemini / OpenCode Google 双模式接入（callback + auth_code_or_url）。
- [x] 2.3 `cli_delegate`：统一新语义映射，不改既有 CLI 行为。
- [x] 2.4 `opencode_auth_cli_flow` 更新 openai 方法入参语义。
- [x] 2.5 orchestrator/registry 模块同步新语义。

## 3. UI / Routes / Models

- [x] 3.1 `models.py` 更新 start 默认 method 与注释语义。
- [x] 3.2 `ui/engines.html` 与 `partials/engines_table.html` 改为新 auth_method 按钮矩阵。
- [x] 3.3 路由层错误文案与新语义一致。

## 4. Tests

- [x] 4.1 更新 `test_engine_auth_flow_manager.py`（新矩阵 + 旧值422）。
- [x] 4.2 更新 `test_v1_routes.py`（新值通过、旧值拒绝）。
- [x] 4.3 更新 `test_ui_routes.py`（按钮与 payload 新值）。
- [x] 4.4 更新 Gemini/Antigravity flow 测试断言（双模式）。

## 5. Docs

- [x] 5.1 更新 `docs/api_reference.md`。
- [x] 5.2 更新 `docs/e2e_example_client_ui_reference.md`。
- [x] 5.3 更新 `docs/containerization.md`。
