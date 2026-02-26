## Context

本 change 以最小可行闭环验证“前端发起 Codex 鉴权”能力。  
核心原则：

1. 不替换现有鉴权路径，只增量增加会话式入口。
2. 不引入跨重启持久化，先用内存 + TTL 控制复杂度。
3. 严格互斥：鉴权会话与 UI 内嵌 TUI 同时最多一个活跃会话。

## Architecture

### 1) EngineAuthFlowManager

新增服务 `server/services/engine_auth_flow_manager.py`，负责：

- 启动 `codex login --device-auth` 子进程。
- 解析 stdout/stderr 中的 device-auth URL 与 user code。
- 跟踪会话状态并提供快照查询。
- 执行取消与超时回收。

会话模型字段：

- `session_id`
- `engine`（首期固定 `codex`）
- `status`：`starting | waiting_user | succeeded | failed | canceled | expired`
- `auth_url`
- `user_code`
- `expires_at`
- `error`
- `auth_ready`
- `started_at | updated_at`

### 2) EngineInteractionGate

新增服务 `server/services/engine_interaction_gate.py`，对“需要独占用户交互注意力的会话”统一加锁：

- scope A: `ui_tui`
- scope B: `auth_flow`

规则：

- 任一 scope 活跃时，另一个 scope 的 `start` 返回冲突。
- terminal 会话结束时释放占用。
- 若占用 session 已 terminal，允许自动清理后重新占用。

`ui_shell_manager` 与 `engine_auth_flow_manager` 均通过该 gate 协调，避免在两个模块内重复散落互斥判断。

### 3) API Surface

`/v1/engines` 新增：

- `POST /auth/sessions`：创建鉴权会话。
- `GET /auth/sessions/{session_id}`：查询会话状态。
- `POST /auth/sessions/{session_id}/cancel`：取消会话。

`/ui/engines` 新增对应代理端点，供页面脚本直接调用。

错误码：

- `401`：Basic Auth 未通过（沿用现有保护）
- `409`：与 TUI 或其它鉴权会话冲突
- `422`：不支持引擎或参数非法
- `404`：会话不存在
- `500`：进程或系统异常

### 4) UI Interaction

在 `/ui/engines` 中新增 Codex 鉴权卡片：

- “连接 Codex”按钮 -> start。
- 显示 `auth_url`、`user_code`、当前状态。
- 状态轮询 -> status。
- 取消按钮 -> cancel。

页面仍保留原有 “在内嵌终端中启动 TUI” 入口；若冲突则展示 409 错误信息。

## Command & Environment

- 命令：`codex login --device-auth`
- 环境：必须走 `RuntimeProfile.build_subprocess_env`，确保 `HOME` 与 XDG 指向隔离 `agent_home`。
- 凭据落盘仍由 Codex CLI 控制，目标为 `<agent_home>/.codex/auth.json`。

## State Machine

### Session transitions

1. `start` -> `starting`
2. 解析到 URL/code 或检测进程存活 -> `waiting_user`
3. 子进程退出且 `auth_ready=true` -> `succeeded`
4. 子进程退出且 `auth_ready=false` -> `failed`
5. 用户 cancel -> `canceled`
6. 超过 TTL -> `expired`

### auth_ready linkage

`auth_ready` 以 `AgentCliManager.collect_auth_status()["codex"]["auth_ready"]` 为准；  
会话状态 `succeeded` 必须同时满足 `process exited` 且 `auth_ready=true`。

## Safety & Observability

- 日志不记录完整敏感片段，仅记录摘要（URL 与 code 可展示给已认证 UI 用户）。
- 会话过期后保留 terminal 快照，便于 UI 诊断。
- 解析失败时保留 stderr 摘要，避免 silent failure。

## Configuration

新增配置（环境变量）：

- `ENGINE_AUTH_DEVICE_PROXY_ENABLED`，默认 `1`
- `ENGINE_AUTH_DEVICE_PROXY_TTL_SECONDS`，默认 `900`

## Rollout

首期默认开启实验能力；若出现回归可通过 `ENGINE_AUTH_DEVICE_PROXY_ENABLED=0` 关闭并回退到既有 TUI/导入流程。
