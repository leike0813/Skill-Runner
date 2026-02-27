## 1. OpenSpec Update

- [x] 1.1 更新 `proposal.md`：明确 OpenAI 2x2 鉴权矩阵范围（codex + opencode/openai）
- [x] 1.2 更新 `design.md`：引入 `auth_method` 契约与分发矩阵
- [x] 1.3 更新三份 delta spec：API/UI/Observability
- [x] 1.4 运行 `openspec validate engine-auth-dual-transport-browser-priority --type change`

## 2. Types & Routing

- [x] 2.1 修改 `server/models.py`：start/snapshot 增加 `auth_method`
- [x] 2.2 修改 `server/routers/engines.py`：start 透传 `auth_method`
- [x] 2.3 修改 `server/routers/ui.py`：start 透传 `auth_method`
- [x] 2.4 保持 `method` 字段兼容，不破坏旧客户端

## 3. Manager Refactor

- [x] 3.1 修改 `server/services/engine_auth_flow_manager.py`：分发键升级为 5 维
- [x] 3.2 codex 实现 2x2：
- [x] 3.2.1 `oauth_proxy + browser-oauth`
- [x] 3.2.2 `oauth_proxy + device-auth`
- [x] 3.2.3 `cli_delegate + browser-oauth`
- [x] 3.2.4 `cli_delegate + device-auth`
- [x] 3.3 opencode/openai 实现 2x2
- [x] 3.4 `input_kind` 与状态语义校正，避免 device 模式错误显示输入框
- [x] 3.5 callback listener 维持会话级动态启停

## 4. OAuth Device Proxy

- [x] 4.1 扩展 `server/services/oauth_openai_proxy_common.py`（device-auth 协议工具）
- [x] 4.2 新增 `server/services/openai_device_proxy_flow.py`
- [x] 4.3 修改 `server/services/codex_oauth_proxy_flow.py`：支持 device token 写盘
- [x] 4.4 修改 `server/services/opencode_openai_oauth_proxy_flow.py`：支持 device token 写盘

## 5. CLI Delegate Adjustment

- [x] 5.1 修改 `server/services/opencode_auth_cli_flow.py`：openai 登录方式按 `auth_method` 精确选项
- [x] 5.2 codex CLI 委托命令支持 `--device-auth`

## 6. UI Matrix

- [x] 6.1 修改 `server/assets/templates/ui/engines.html`：codex/opencode-openai 四按钮矩阵
- [x] 6.2 请求体新增 `auth_method` 传递
- [x] 6.3 输入提示文案按 `auth_method` 区分
- [x] 6.4 提交后隐藏输入区与链接逻辑不回归

## 7. Tests

- [x] 7.1 更新 `tests/unit/test_engine_auth_flow_manager.py`：覆盖 codex/opencode-openai 2x2
- [x] 7.2 更新 `tests/unit/test_v1_routes.py` 与 `tests/unit/test_ui_routes.py`：`auth_method` 透传
- [x] 7.3 更新 `tests/unit/test_opencode_auth_cli_flow.py`：openai device/browser 选择
- [x] 7.4 新增/更新 OpenAI device proxy 单测
- [x] 7.5 执行回归测试（含 gemini/iflow/opencode 非 openai）

## 8. Docs

- [x] 8.1 更新 `docs/api_reference.md`：2x2 与 `auth_method` 契约
- [x] 8.2 更新 `docs/containerization.md`：browser fallback 与 device 流程说明
- [x] 8.3 更新 `docs/e2e_example_client_ui_reference.md`：引擎管理 UI 矩阵入口说明
