## 1. OpenSpec artifacts

- [x] 1.1 完成 proposal，锁定 Gemini Phase 1 范围与约束。
- [x] 1.2 完成 design，定义 PTY driver、状态机、提交动作与判定规则。
- [x] 1.3 完成 delta specs（`ui-engine-management`、`management-api-surface`、`engine-auth-observability`）。
- [x] 1.4 运行 `openspec validate engine-auth-cli-delegation-gemini-phase1 --type change` 并通过。

## 2. Backend implementation

- [x] 2.1 新增 `gemini_auth_cli_flow`，实现 PTY 启动、输出解析、自动输入与 submit 写入。
- [x] 2.2 扩展 `engine_auth_flow_manager` 支持 gemini strategy + submit 统一入口。
- [x] 2.3 扩展 `server/models.py` 增加 submit 请求/响应模型。
- [x] 2.4 扩展 `/v1/engines` 新 submit 端点（Basic Auth 保护）。
- [x] 2.5 扩展 `/ui/engines` 新 submit 端点并保持现有行为兼容。

## 3. UI

- [x] 3.1 更新 Engine 管理页：新增 Gemini 连接入口。
- [x] 3.2 更新鉴权面板：支持 URL 展示、authorization code 输入与提交。
- [x] 3.3 保持 Codex 现有交互不回归，保留 auth 与 TUI 互斥提示。

## 4. Tests and verification

- [x] 4.1 新增 `test_gemini_auth_cli_flow.py` 覆盖 Gemini 状态机关键路径。
- [x] 4.2 更新 `test_v1_routes.py` 覆盖 submit 端点与错误码。
- [x] 4.3 更新 `test_ui_routes.py` 覆盖 UI submit 路由与页面元素。
- [x] 4.4 运行目标 pytest 集与 mypy（变更文件集）并通过。
