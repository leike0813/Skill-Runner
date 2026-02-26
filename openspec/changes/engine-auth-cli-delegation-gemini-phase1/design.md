## Context

本 change 在既有 `engine_auth_flow_manager` 基础上新增 Gemini driver。  
设计目标：

1. Gemini 鉴权链路不依赖 ttyd，不复用 UI shell 输入通道。
2. 鉴权成功判定仅依赖 CLI 输出锚点。
3. 与 `auth-status` 文件判定解耦，避免双重语义互相污染。

## Architecture

### 1) GeminiAuthCliFlow（新服务）

新增 `server/services/gemini_auth_cli_flow.py`，负责：

- 启动 `gemini --screen-reader` 子进程（PTY 模式）。
- 后台读取 PTY 输出，执行 ANSI 清洗与锚点解析。
- 自动输入：
  - 未鉴权菜单场景自动 `Enter`（选择默认 Login with Google）。
  - 启动即主界面场景自动输入 `/auth login` 并回车。
- 暴露 `submit_code()`，把用户提交的 authorization code 写入 PTY。
- 维护 Gemini 专用状态机与超时/取消处理。

### 2) EngineAuthFlowManager（扩展）

- 保留 Codex 现有 device-auth 分支。
- 新增 Gemini 分支分发：
  - `engine=gemini`
  - `method=screen-reader-google-oauth`
- 新增统一入口 `submit_session(session_id, code)`。
- 会话互斥仍由 `EngineInteractionGate` 统一控制。

### 3) API 扩展

`/v1/engines` 新增：

- `POST /auth/sessions/{session_id}/submit`

`/ui/engines` 新增：

- `POST /auth/sessions/{session_id}/submit`

submit 语义：

- 仅 Gemini screen-reader 会话支持。
- 其他引擎/方法返回 `422`。

## Gemini 状态机

状态集合：

- `starting`
- `waiting_user`
- `waiting_user_code`
- `code_submitted_waiting_result`
- `succeeded`
- `failed`
- `canceled`
- `expired`

关键迁移：

1. start -> `starting`
2. 检测未鉴权菜单并自动 Enter -> `waiting_user`
3. 解析 URL + `Enter the authorization code:` -> `waiting_user_code`
4. submit code -> `code_submitted_waiting_result`
5. 再次检测主界面锚点 -> `succeeded`
6. 异常/EOF/退出/超时 -> `failed|expired`
7. cancel -> `canceled`

## Success Rule

Gemini 会话 `succeeded` 必须满足：

- 已提交 authorization code；
- PTY 输出出现主界面锚点（`Type your message or @path/to/file`）。

不使用以下信号作为成功条件：

- auth 文件存在性；
- `GET /v1/engines/auth-status` 结果。

## Output Parsing

锚点（首期固定）：

- `How would you like to authenticate for this project?`
- `(Use Enter to select)`
- `Please visit the following URL to authorize the application:`
- `Enter the authorization code:`
- `Type your message or @path/to/file`

URL 解析策略：

- 从 URL 提示段到 code 提示段做窗口截取；
- 多行拼接 + 去空白 + ANSI 清洗后提取 `https://...`；
- 处理 URL 被换行折断场景。

## Safety

- 会话 TTL 沿用现有配置（默认 900s）。
- 取消/过期强制结束进程组并释放互斥门。
- 日志中仅保留会话调试摘要，不新增凭据文件读取。
