## 1. OpenSpec artifacts

- [x] 1.1 完成 proposal，锁定 OpenCode Phase 1 provider 范围与 `/input` 迁移。
- [x] 1.2 完成 design，明确 OpenCode API key/OAuth 分流与 Google 清理规则。
- [x] 1.3 完成 delta specs（`management-api-surface`、`ui-engine-management`、`engine-auth-observability`）。
- [x] 1.4 运行 `openspec validate engine-auth-opencode-provider-phase1 --type change` 并通过。

## 2. Backend implementation

- [x] 2.1 新增 `opencode_auth_provider_registry.py` 与 provider 配置文件。
- [x] 2.2 新增 `opencode_auth_store.py`（API key 原子写入 + antigravity 清理）。
- [x] 2.3 新增 `opencode_auth_cli_flow.py`（OAuth PTY 编排）。
- [x] 2.4 扩展 `engine_auth_flow_manager.py`：
  - `start_session(..., provider_id)`
  - `input_session(...)`
  - 注册 OpenCode driver
- [x] 2.5 删除 `submit_session(...)` 调用路径。

## 3. API + UI implementation

- [x] 3.1 `server/models.py` 新增 input 请求/响应模型，移除 submit 模型。
- [x] 3.2 `server/routers/engines.py` 与 `server/routers/ui.py` 新增 `/input` 并删除 `/submit`。
- [x] 3.3 更新 `server/assets/templates/ui/engines.html`：
  - OpenCode provider 下拉
  - 统一 input 提交
  - 保持提交后隐藏输入区与链接
- [x] 3.4 更新 `engines_table.html` 增加 OpenCode 鉴权按钮。

## 4. Tests and verification

- [x] 4.1 新增 `test_opencode_auth_store.py`。
- [x] 4.2 新增 `test_opencode_auth_cli_flow.py`。
- [x] 4.3 更新 `test_engine_auth_flow_manager.py` 覆盖 input 分发与 OpenCode 分流。
- [x] 4.4 更新 `test_v1_routes.py`、`test_ui_routes.py`：`/input` 与 `/submit` 删除回归。
- [x] 4.5 执行变更相关 pytest。
- [x] 4.6 执行改动文件集 mypy。
