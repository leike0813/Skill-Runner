## Why

当前 Engine Auth 会话链路已覆盖 Codex/Gemini/iFlow，但 OpenCode 仍缺少前端可直接触发的 provider 鉴权能力。  
同时，现有 Gemini/iFlow 使用 `/submit`，接口语义无法覆盖 API Key 与通用文本输入，导致新增 provider 流程时出现接口分叉。

为降低使用门槛并统一输入语义，本 change 在不改动 `auth-status` 既有判定逻辑的前提下落地：

1. OpenCode provider 鉴权（Phase 1）；
2. 全引擎鉴权输入统一到 `/input`；
3. 废弃并删除旧 `/submit`；
4. Google AntiGravity OAuth 前执行全局账号清理，降低多账号状态机复杂度。

## What Changes

- 新增 OpenCode provider registry（固定首批）与后端编排：
  - OAuth: `openai`, `google`
  - API Key: `deepseek`, `iflowcn`, `minimax`, `moonshotai`, `opencode`, `openrouter`, `zai-coding-plan`
- 新增 OpenCode API Key 直写存储服务（原子写入 `auth.json`）。
- 新增 OpenCode OAuth PTY driver（openai/google）。
- Google AntiGravity OAuth 前置清理 `antigravity-accounts.json` 账户集合，并产生日志审计。
- 新增统一输入接口：
  - `POST /v1/engines/auth/sessions/{id}/input`
  - `POST /ui/engines/auth/sessions/{id}/input`
- 删除旧接口：
  - `POST /v1/engines/auth/sessions/{id}/submit`
  - `POST /ui/engines/auth/sessions/{id}/submit`
- Engine 管理页新增 OpenCode provider 选择与统一输入提交流程。

## Capabilities

### New Capabilities

- `engine-auth-opencode-provider-phase1`: OpenCode provider auth（OAuth + API Key）与统一输入接口。

### Modified Capabilities

- `management-api-surface`: auth session 输入接口从 `submit` 迁移到 `input`。
- `ui-engine-management`: OpenCode provider 入口、统一 input 提交与状态展示。
- `engine-auth-observability`: 新增 OpenCode provider 会话可观测字段与 Google 清理审计字段。

## Scope

### In Scope

- OpenCode provider 鉴权首批范围。
- `/input` 统一输入语义，覆盖 Gemini/iFlow/OpenCode。
- 删除 `/submit` 端点（v1/ui 同步）。
- Google AntiGravity 清理动作（仅目标账号文件）。

### Out of Scope

- `opencode mcp auth` 链路。
- OpenCode 全 provider 覆盖（首期仅固定清单）。
- `auth-status` 逻辑重构。

## Impact

- 主要变更：
  - `server/models.py`
  - `server/routers/engines.py`
  - `server/routers/ui.py`
  - `server/services/engine_auth_flow_manager.py`
  - 新增 OpenCode auth 相关服务与配置文件
  - `server/assets/templates/ui/engines.html`
  - 路由与服务单测更新
- 对旧客户端存在破坏性影响：调用 `/submit` 将失败（符合本次“直接废弃”决策）。
