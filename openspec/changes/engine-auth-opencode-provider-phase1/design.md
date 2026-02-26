## Context

现有鉴权会话框架由 `EngineAuthFlowManager` 统一调度，Gemini/iFlow 通过 PTY driver 完成“后台编排 + 用户输入回填”。  
OpenCode Phase 1 沿用该框架，新增 provider 维度与 API Key 快路径，并将全引擎用户输入统一为 `/input`。

## Design Decisions

1. **统一输入契约**：所有会话输入走 `input(kind, value)`，废弃 `submit(code)`。
2. **OpenCode 分流**：
   - API Key provider：不启动 PTY，直接进入 `waiting_user`，由 `/input(kind=api_key)` 写入 `auth.json` 后 `succeeded`。
   - OAuth provider：启动 `opencode auth login` PTY，编排菜单并在 URL+输入点进入 `waiting_user`。
3. **Google 清理前置**：`provider=google` 在启动 OAuth 前必须清理 `antigravity-accounts.json` 账户集合；失败即会话 `failed`。
4. **状态语义统一**：
   - `waiting_orchestrator`：后台自动输入进行中；
   - `waiting_user`：已到达用户输入阶段（URL/API key/code）；
   - `code_submitted_waiting_result`：已回填等待 CLI 收敛。
5. **安全要求**：输入值（尤其 API key）不得写入日志或错误摘要。

## Architecture

### 1) EngineAuthFlowManager 扩展

- `start_session(engine, method, provider_id=None)`
- `input_session(session_id, kind, value)`
- 维护会话快照增量字段：
  - `provider_id`
  - `provider_name`
  - `input_kind`
  - `audit`（可选审计信息）
- driver 分发扩展为 `codex|gemini|iflow|opencode`。

### 2) OpenCode Provider Registry

- 配置文件：`server/assets/configs/opencode/auth_providers.json`
- 服务：`opencode_auth_provider_registry.py`
- 输出：`provider_id/display_name/auth_mode/menu_label`

### 3) OpenCode Auth Store

- 服务：`opencode_auth_store.py`
- 原子写入：
  - `<agent_home>/.local/share/opencode/auth.json`
- API Key 写入结构：
  - `{ "<provider>": { "type":"api", "key":"..." } }`
- Google 清理：
  - `<agent_home>/.config/opencode/antigravity-accounts.json`
  - 清空 `accounts`，重置 `active`（若存在）。

### 4) OpenCode OAuth PTY Driver

- 服务：`opencode_auth_cli_flow.py`
- 启动命令：`opencode auth login`
- 编排流程：
  - provider 菜单定位并选择目标 provider。
  - `openai`：选择 OAuth 登录项，等待 URL + redirect/code 输入提示。
  - `google`：选择 `OAuth with Google (Antigravity)` -> `Add account` -> `Project ID` 回车空值 -> URL + 输入提示。
- 用户回填：
  - `/input(kind=text,value=...)` 写入 PTY 并回车。
- 收敛判定：
  - 提交后出现成功锚点，或进程正常退出且 `auth_ready=true`。

## API Contract Changes

### Added

- `POST /v1/engines/auth/sessions/{session_id}/input`
- `POST /ui/engines/auth/sessions/{session_id}/input`
- `EngineAuthSessionInputRequest`
- `EngineAuthSessionInputResponse`
- `start_session` 请求增加可选 `provider_id`（OpenCode 使用）

### Removed

- `POST /v1/engines/auth/sessions/{session_id}/submit`
- `POST /ui/engines/auth/sessions/{session_id}/submit`

## Failure Handling

- provider 不支持 -> `422`
- 输入 kind 与会话阶段不匹配 -> `422`
- AntiGravity 清理失败 -> 会话 `failed`（带审计）
- 会话不存在 -> `404`
- 与 TUI/其他 auth 会话冲突 -> `409`

## Compatibility

- `start/status/cancel` 保持兼容；
- `/submit` 明确移除，旧客户端需迁移到 `/input`。
