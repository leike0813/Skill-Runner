## 1. OpenSpec artifacts

- [x] 1.1 完成 proposal，锁定 iFlow Phase 1 范围、约束与 method 命名。
- [x] 1.2 完成 design，定义 PTY driver、状态机、菜单纠偏与成功判定。
- [x] 1.3 完成 delta specs（`ui-engine-management`、`management-api-surface`、`engine-auth-observability`）。
- [x] 1.4 运行 `openspec validate engine-auth-cli-delegation-iflow-phase1 --type change` 并通过。

## 2. Backend implementation

- [x] 2.1 新增 `iflow_auth_cli_flow.py`，实现 PTY 启动、输出解析、自动输入、submit 写入。
- [x] 2.2 扩展 `engine_auth_flow_manager.py` 支持 iflow strategy 分发与 submit。
- [x] 2.3 保持会话 gate 互斥语义，不新增并行 auth 会话。
- [x] 2.4 保持 `auth-status` 逻辑不变，仅改会话成功判定路径。

## 3. API + UI implementation

- [x] 3.1 扩展 `/v1/engines/auth/sessions` 支持 `engine=iflow, method=iflow-cli-oauth`。
- [x] 3.2 扩展 submit 路径支持 iFlow 会话。
- [x] 3.3 更新 Engine 管理页：新增“连接 iFlow”入口与 method 解析。
- [x] 3.4 更新提交区显示逻辑：iFlow 在等待用户授权码时展示 submit。

## 4. Tests and verification

- [x] 4.1 新增 `test_iflow_auth_cli_flow.py` 覆盖菜单识别/方向键纠偏/URL/submit/模型页自动回车。
- [x] 4.2 更新 `test_engine_auth_flow_manager.py` 覆盖 iflow start/submit/success/error 路径。
- [x] 4.3 更新 `test_v1_routes.py`、`test_ui_routes.py` 覆盖 iflow 鉴权会话接口。
- [x] 4.4 运行变更相关 pytest。
- [x] 4.5 运行变更文件集 mypy 并通过。
