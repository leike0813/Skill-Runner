## Context

当前 `/ui/engines` 鉴权交互使用“硬编码按钮矩阵”：
1. 按引擎/transport/auth_method直接铺开；
2. 页面中同时存在引擎内入口和状态区入口；
3. 方式选择缺少统一前置上下文（transport）。

这会放大交互复杂度，并且在能力矩阵变化时引发前端硬编码回归。

## Design

### 1) 全局 transport 选择器

在 Engine Auth 状态卡片顶部引入全局下拉：
1. `oauth_proxy`（默认）
2. `cli_delegate`

交互规则：
1. 该选择器仅影响后续新发起会话。
2. 若存在活动 auth 会话或活动 TUI 会话，选择器禁用。
3. 会话结束后恢复可选。

### 2) 引擎单入口 + 分层菜单

引擎表格 Actions 列中每个引擎保留一个入口按钮：
1. `连接 Codex`
2. `连接 Gemini`
3. `连接 iFlow`
4. `连接 OpenCode`

菜单渲染：
1. 非 OpenCode：按钮点击后直接展示“当前 transport 可用 auth_method 列表”。
2. OpenCode：先展示 provider 列表，再展示 provider 对应 auth_method 列表。

### 3) UI 能力矩阵单源

由 `server/routers/ui.py` 注入 `auth_ui_capabilities`：
1. 结构：`transport -> engine -> (provider -> methods | methods)`
2. 菜单只读此对象，不再前端猜测默认方式。
3. OpenCode provider 列表继续用 `opencode_auth_providers`，并与能力矩阵交叉过滤。

### 4) 状态窗口布局

状态窗口保留：
1. 引擎/链路/方式/状态
2. auth URL
3. user code
4. expires_at
5. 输入提示与输入框（按当前会话语义）
6. 错误信息

按钮策略：
1. 只保留取消按钮（移到顶部，和 transport 下拉同一行）。
2. 移除所有“启动鉴权”按钮。

### 5) user_code 复制按钮

显示条件：
1. `session.user_code` 存在
2. `auth_method == auth_code_or_url`
3. `engine == codex` 或 `engine == opencode && provider_id == openai`

复制策略：
1. 优先 `navigator.clipboard.writeText`
2. fallback 到 `textarea + execCommand("copy")`
3. 显示轻量结果反馈

### 6) 输入提示细化

1. `callback`：提示“自动回调优先，异机可粘贴回调 URL 兜底”。
2. `auth_code_or_url`：
   - `codex`/`opencode+openai`：device-code 场景通常无输入框（以 `input_kind` 为准）。
   - `gemini`：提示粘贴授权码。
   - `opencode+google`：提示粘贴完整 localhost 回调 URL。
   - `iflow`：提示可粘贴授权码或回调 URL。

## Risks

1. UI 能力矩阵与后端校验若暂时不一致，可能出现前端可选但后端 422。
2. htmx 表格异步刷新后按钮重新渲染，需要在脚本中重复应用禁用态。
3. 不同浏览器剪贴板权限策略不同，复制按钮需保留 fallback。

## Mitigations

1. 前端对 422 统一展示后端错误，不做静默失败。
2. 在 `htmx:afterSwap` 事件重新应用按钮禁用状态。
3. 复制失败时给出明确提示，不影响会话主流程。
