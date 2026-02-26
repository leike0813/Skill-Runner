## Why

当前实验性 CLI 委托编排鉴权仅覆盖 Codex 与 Gemini。  
iFlow 也具备可编排的 TUI 鉴权路径，但其输出包含 ANSI 控制字符，且存在菜单选中项漂移（`●` 可能不在第一项）。  
为降低鉴权门槛并保持与现有鉴权会话体系一致，需要新增 iFlow Phase 1：

1. 仅支持 OAuth 菜单第一项自动流；
2. 复用现有 auth session API（start/status/cancel/submit）；
3. 成功判定仅基于 CLI 输出锚点，不与 auth-status 文件判定耦合。

## What Changes

- 新增 iFlow 鉴权 driver：`iflow` + PTY I/O 编排（非 ttyd 链路）。
- 新增 method：`iflow-cli-oauth`。
- 会话自动化能力：
  - 若启动即主界面，自动注入 `/auth` 进入鉴权菜单；
  - 解析菜单 `● n.`，若非第 1 项自动方向键纠偏至第 1 项后回车；
  - OAuth 页解析 URL 与授权码输入态；
  - 提交授权码后自动处理模型选择页（回车默认模型）。
- `submit` 从 Gemini-only 扩展为 Gemini + iFlow。
- 保持 `GET /v1/engines/auth-status` 既有实现不变。

## Capabilities

### New Capabilities

- `engine-auth-cli-delegation-iflow-phase1`: iFlow CLI 委托编排鉴权（Phase 1）。

### Modified Capabilities

- `management-api-surface`: auth session `submit` 扩展支持 iFlow 会话。
- `ui-engine-management`: Engine 管理页新增 iFlow 连接入口与会话交互。
- `engine-auth-observability`: 增加 iFlow 委托编排的状态与观测语义。

## Scope

### In Scope

- 引擎：`iflow`
- method：`iflow-cli-oauth`
- 会话接口：`start/status/cancel/submit`
- 菜单选中项识别与纠偏（`● n.`）
- OAuth URL 提取与授权码提交
- 模型选择页默认回车

### Out of Scope

- iFlow API Key / 其他鉴权选项自动化
- 修改 `auth-status` 判定逻辑
- callback 模式 OAuth
- ttyd 输入通道复用

## Impact

- 主要影响 `server/services/engine_auth_flow_manager.py` 与新增 `iflow_auth_cli_flow.py`。
- UI 增量影响 `server/assets/templates/ui/engines.html` 与 `engines_table.html`。
- 路由与模型接口保持兼容，仅新增 iFlow 参数组合与 submit 支持范围。
