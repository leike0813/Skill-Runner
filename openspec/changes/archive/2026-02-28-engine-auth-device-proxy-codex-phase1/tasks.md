## 1. OpenSpec artifacts

- [x] 1.1 完成 proposal，锁定首期范围为 codex + device-auth。
- [x] 1.2 完成 design，定义会话状态机、互斥门控、接口与错误语义。
- [x] 1.3 完成 delta specs（`ui-engine-management`、`engine-auth-observability`、`management-api-surface`）。
- [x] 1.4 执行 `openspec validate engine-auth-device-proxy-codex-phase1 --type change` 并通过。

## 2. Backend implementation

- [x] 2.1 新增 `engine_interaction_gate`，提供 auth/tui 全局互斥控制。
- [x] 2.2 新增 `engine_auth_flow_manager`，实现 start/status/cancel + TTL + URL/code 解析。
- [x] 2.3 扩展 `server/models.py` 增加 auth session 请求/响应模型。
- [x] 2.4 扩展 `/v1/engines` 新端点（受 Basic Auth 保护）。
- [x] 2.5 扩展 `/ui` 新端点并注入页面会话快照。
- [x] 2.6 将 `ui_shell_manager` 接入统一 gate，保证双向冲突检测。

## 3. UI and config

- [x] 3.1 修改 `ui/engines.html` 与 `ui/partials/engines_table.html` 增加 “连接 Codex” 交互。
- [x] 3.2 增加前端轮询与取消动作，展示 URL/code/status/error。
- [x] 3.3 新增配置项默认值（enabled/ttl），并保持开关可关闭。

## 4. Tests and verification

- [x] 4.1 新增/更新 `test_engine_auth_flow_manager.py` 覆盖状态机主路径。
- [x] 4.2 更新 `test_v1_routes.py` 覆盖新 API 权限、冲突与错误码。
- [x] 4.3 更新 `test_ui_routes.py` 覆盖 UI auth session 端点与页面渲染。
- [x] 4.4 更新 `test_ui_shell_manager.py` 或新增 gate 测试覆盖 auth/tui 互斥。
- [x] 4.5 运行相关 pytest 与类型检查，确保无回归。
