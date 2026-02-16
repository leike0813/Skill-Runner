## Context

当前系统已经具备三类能力：
- Skill 管理（安装、列表、详情）；
- Engine 管理（模型、升级、认证状态）；
- Run 管理（提交、状态、日志、产物、文件浏览）。

但这些能力分散在：
- `v1` 业务接口（偏执行链路）；
- `ui` 路由（偏内置网页渲染）。

对外部前端而言，缺少一组“前端无关、稳定字段、可直接驱动管理页”的统一接口面。

## Goals

1. 定义统一管理 API 面，支持 Skill / Engine / Run 三域。
2. 明确 `/ui/*` 是适配层，不作为多前端复用契约。
3. 为 Run 管理提供“对话窗口”所需的统一数据动作：
   - 状态与交互信息；
   - SSE 日志流；
   - pending/reply；
   - 文件树与文件预览。
4. 保持现有功能范围不变，仅重构接口分层与契约。

## Non-Goals

1. 不新增前端页面或前端框架改造。
2. 不改变引擎执行语义或调度策略。
3. 不移除旧接口（本阶段以兼容为前提）。

## Prerequisite

- `interactive-25-api-sse-log-streaming` 已定义并落地 Run 日志 SSE 契约。
- `interactive-26-job-termination-api-and-frontend-control` 已提供前端可调用的 Job 终止原语。
- `interactive-20-adapter-turn-protocol-and-mode-aware-patching` 与 `interactive-10-orchestrator-waiting-user-and-slot-release` 已定义 interactive 核心运行语义。

## Design

### 1) 分层原则

- **Domain API（通用层）**：`/v1/management/*`，面向任意前端。
- **UI Adapter（渲染层）**：`/ui/*`，消费 Domain API/Service 并产出 HTML。

约束：
- 新增管理页能力优先进入 Domain API；
- `/ui/*` 不再承载新增“仅 UI 可见”的核心业务语义。

### 2) 统一资源模型（Management DTO）

#### Skill 管理
- `SkillSummary`：`id,name,version,engines,installed_at,health`
- `SkillDetail`：在 `SkillSummary` 基础上补充 `schemas,entrypoints,files`

#### Engine 管理
- `EngineSummary`：`engine,cli_version,auth_ready,sandbox_status,models_count`
- `EngineDetail`：在 `EngineSummary` 基础上补充 `models,upgrade_status,last_error`

#### Run 管理（对话窗口核心）
- `RunConversationState`：
  - `request_id,run_id,status,engine,skill_id,updated_at`
  - `pending_interaction_id?`
  - `interaction_count`
  - `poll_logs`（兼容轮询策略）
- `RunExplorerState`：
  - `entries`（文件树）
  - `preview`（按路径预览）
- `RunStreamState`：
  - SSE 连接状态
  - `stdout_offset/stderr_offset`

### 3) Run 管理动作统一

将现有动作在管理 API 下统一聚合（可内部复用旧 router/service）：
- `GET /v1/management/runs/{request_id}`（统一 run 状态与交互态）
- `GET /v1/management/runs/{request_id}/files`
- `GET /v1/management/runs/{request_id}/file?path=...`
- `GET /v1/management/runs/{request_id}/events`（复用 `interactive-25` SSE）
- `GET /v1/management/runs/{request_id}/pending`
- `POST /v1/management/runs/{request_id}/reply`
- `POST /v1/management/runs/{request_id}/cancel`（复用 `interactive-26` 取消语义）

说明：
- `pending/reply` 与既有 `/v1/jobs/*` interactive 端点语义一致；
- 管理 API 侧重“前端友好聚合”，不是替代底层执行 API。

### 4) 迁移与兼容策略

- 第一阶段：新增 `management` API，同时保留旧 `v1` 与 `ui` 路由；
- 第二阶段：`/ui/*` 优先改为消费 `management` API 形态（可服务内调用）；
- 不在本 change 执行删除动作，只补充弃用说明。

## Risks & Mitigations

1. **风险：接口重复导致维护成本上升**
   - 缓解：通过共享 service/DTO，限制重复业务逻辑。
2. **风险：管理 API 与旧接口语义漂移**
   - 缓解：为关键资源建立字段映射测试与契约测试。
3. **风险：Run 对话窗口接口边界不清**
   - 缓解：明确“状态/动作/流”三类接口职责，避免混杂。
