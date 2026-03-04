# 会话中鉴权重构断点记录（2026-03-03）

## 目的

本文件用于在中断当前实现任务前，固化关键上下文、已确认事实、未完成改动和推荐续做顺序。

本轮任务目标对应的 OpenSpec change 为：

- `refine-in-conversation-auth-method-selection-and-session-timeout`

本轮**尚未执行任何代码修改**。  
目前只完成了代码搜索、设计核对、接口与测试对齐分析。

---

## 当前目标

当前需要实现的是对已落地的 `waiting_auth` 流程做第二轮收敛，核心方向如下：

1. 不做客户端 capability 协商
2. 进入 `waiting_auth` 后，先让用户显式选择 auth method
3. auth timeout 改成 auth session 级，而不是 `waiting_auth` 状态级
4. 前端 timeout 以 backend 为唯一真相来源
5. 新增 auth session 状态接口，供前端在创建 session 后和断线重连后重新同步
6. 修复当前已知问题：
   - submit 点击无响应
   - callback 流被错误显示成“授权码”
   - `codex/gemini/iflow/opencode+deepseek` 高置信度 `auth_detection` 未稳定进入 `waiting_auth`
   - 活跃 auth session 残留时后续请求失败但缺少明确错误

---

## 已确认的高价值事实

### 1. `run_auth_orchestration_service.py` 当前缺失

当前仓库中：

- `server/services/orchestration/run_auth_orchestration_service.py`

不存在，但已有多个调用点和测试都在引用它：

- `server/services/orchestration/job_orchestrator.py`
- `server/services/orchestration/run_interaction_service.py`
- `server/routers/oauth_callback.py`
- `tests/unit/test_run_auth_orchestration_service.py`

这意味着下一轮实现的第一个关键文件就是它。

---

### 2. `server/models/interaction.py` 已经提前对齐了大半协议

当前该文件已经包含：

- `AuthMethod`
  - `callback`
  - `device_auth`
  - `authorization_code`
  - `api_key`
- `AuthSessionPhase`
  - `method_selection`
  - `challenge_active`
- `AuthSubmissionKind`
  - `callback_url`
  - `authorization_code`
  - `api_key`
- `PendingAuthMethodSelection`
- `PendingAuth`
- `AuthMethodSelection`
- `AuthSessionStatusResponse`
- `InteractionReplyRequest`
  - 已支持 `mode=auth` 下的 `selection` / `submission` union

结论：

- 核心协议模型已经基本就位
- 下一轮重点不是重新定义 interaction 模型，而是把 service、router、front-end 接上

---

### 3. `server/models/__init__.py` 目前是滞后的

当前该文件还没有把一批新的 interaction/auth 类型导出：

至少需要补齐：

- `AuthMethod`
- `AuthSessionPhase`
- `PendingAuthMethodSelection`
- `AuthMethodSelection`
- `AuthSessionStatusResponse`

否则：

- `server/routers/jobs.py`
- `server/services/orchestration/run_interaction_service.py`

这类通过 `server.models` 聚合导入的文件会继续受限。

---

### 4. `run_store.py` 已经有相当多的基础设施

当前已存在的方法：

- `set_pending_auth(...)`
- `get_pending_auth(...)`
- `clear_pending_auth(...)`
- `set_pending_auth_method_selection(...)`
- `get_pending_auth_method_selection(...)`
- `clear_pending_auth_method_selection(...)`
- `set_auth_resume_context(...)`
- `get_auth_resume_context(...)`
- `clear_auth_resume_context(...)`
- `get_request_id_for_auth_session(...)`
- `get_auth_session_status(request_id)`

其中：

- `pending_auth_method_selection`
- `pending_auth`

对应的数据表与持久化入口都已经存在。

当前缺口：

- `get_auth_session_status(request_id)` 只返回非常基础的 phase 信息
- 还没有返回 backend 为真相的 timeout/status 视图，例如：
  - `waiting_auth`
  - `timed_out`
  - `available_methods`
  - `selected_method`
  - `auth_session_id`
  - `challenge_kind`
  - `timeout_sec`
  - `created_at`
  - `expires_at`
  - `server_now`
  - `last_error`

---

### 5. `run_interaction_service.py` 仍然是旧语义

当前问题：

1. `get_pending()` 只返回：
   - `pending`
   - `pending_auth`
   没有：
   - `pending_auth_method_selection`

2. `submit_reply()` 的 `mode=auth` 分支只支持：
   - 直接 auth submission
   - 要求 `request.submission` 和 `request.auth_session_id`
   - 不支持 `selection`

这与当前 `InteractionReplyRequest` 新 union 模型不一致。

结论：

- 下一轮必须修改 `server/services/orchestration/run_interaction_service.py`
- 让它：
  - 返回 `pending_auth_method_selection`
  - 支持 `auth method selection`
  - 支持 `auth session status` 查询的配套调用

---

### 6. `jobs.py` 目前没有 auth session 状态接口

需要新增：

- `GET /v1/jobs/{request_id}/auth/session`

当前已有：

- `GET /jobs/{request_id}/interaction/pending`
- `POST /jobs/{request_id}/interaction/reply`

所以该路由应放在：

- `server/routers/jobs.py`

并尽量复用现有 installed source adapter 语义。

---

### 7. `oauth_callback.py` 已经预留了 run-scoped 完成回调的调用点

当前它已经调用：

- `run_auth_orchestration_service.handle_callback_completion(...)`

需要的新 service 方法签名基本已经被路由锁定：

- `handle_callback_completion(snapshot, append_orchestrator_event, update_status, resume_run_job)`

结论：

- 新 service 必须兼容这个调用点

---

### 8. 各 engine 当前真实支持的 auth method

#### Codex

文件：

- `server/engines/codex/auth/runtime_handler.py`

当前支持：

- `callback`
- `auth_code_or_url`

但实际语义应对外展示为：

- `callback`
- `device_auth`

原因：

- `callback` 路径接受 `text`，适合自动 callback + 手工粘贴 callback URL
- `auth_code_or_url` 更接近 device auth，不适合聊天内粘贴授权码

#### Gemini

文件：

- `server/engines/gemini/auth/runtime_handler.py`

当前支持：

- `callback`
- `auth_code_or_url`

对外应展示为：

- `callback`
- `authorization_code`

其中：

- `callback` -> `text`
- `auth_code_or_url` -> `code`

#### iFlow

文件：

- `server/engines/iflow/auth/runtime_handler.py`

当前支持：

- `callback`
- `auth_code_or_url`

对外应展示为：

- `callback`
- `authorization_code`

#### OpenCode

文件：

- `server/engines/opencode/auth/runtime_handler.py`

应按 provider 区分：

- `openai`
  - `callback`
  - `device_auth`
- `google`
  - `callback`
- 其他 API-key-only provider
  - `api_key`

---

### 9. `engine_auth_flow_manager.py` 已经有 session TTL / expires_at

文件：

- `server/services/engine_management/engine_auth_flow_manager.py`

已确认：

- manager 自己有 session TTL
- TTL 来源于：
  - `ENGINE_AUTH_DEVICE_PROXY_TTL_SECONDS`
- 各 session snapshot 带：
  - `created_at`
  - `expires_at`
  - `status`
  - `input_kind`
  - `auth_url`
  - `user_code`
  - `error`
- 会抛：
  - `EngineInteractionBusyError`

结论：

- 不必再发明一套 timeout 真相机制
- 下一轮应直接把这里的 session truth 投射成 run 侧接口

---

### 10. 当前前端问题的直接根因

文件：

- `e2e_client/templates/run_observe.html`

已确认：

1. `submitReply()` 对非 2xx 响应直接：
   - `if (!res.ok) return;`
   所以用户看到的是“点击 submit 没反应”

2. 前端当前只支持旧 auth challenge 语义：
   - 没有 method selection phase
   - 没有 auth session 状态同步
   - 对 callback/manual callback URL 和 authorization_code 区分不足

3. 当前表单隐藏字段只有：
   - `interaction-id`
   - `auth-session-id`
   - `auth-input-kind`

没有：

- auth method selection
- phase
- auth session truth resync

---

### 11. 当前 `run_job_lifecycle_service.py` 仍然假设“进入 waiting_auth 就已经有具体 auth session”

关键代码行为：

- 高置信度 `auth_detection` 后直接调用：
  - `self.auth_orchestration_service.create_pending_auth(...)`
- 然后根据是否返回 `PendingAuth` 决定是否进入：
  - `RunStatus.WAITING_AUTH`

这不适合新的两段式语义，因为下一轮应该支持：

1. `method_selection`
2. `challenge_active`

也就是说：

- 进入 `waiting_auth` 不应再等价于“已经创建好 auth session”
- 对多方法 engine/provider，应先返回 `pending_auth_method_selection`

---

### 12. `run_recovery_service.py` 目前只会保留 `pending_auth`

当前恢复逻辑：

- 若 `run_status == WAITING_AUTH`
- 只检查 `get_pending_auth(request_id)`

这不够。

下一轮必须扩展为：

- 若存在 `pending_auth_method_selection`
  或 `pending_auth`
  都要把该 run 视为可恢复的 `waiting_auth`

---

### 13. `runtime_event` / `factories` 仍然是旧 auth payload 形态

文件：

- `server/models/runtime_event.py`
- `server/runtime/protocol/factories.py`

当前缺口：

- `auth` payload 还没有统一承载：
  - `phase`
  - `available_methods`
  - `selected_method`
  - `timeout_sec`
  - `created_at`
  - `expires_at`

`OrchestratorEventType` 也缺少若干这轮应该有的事件：

- `AUTH_METHOD_SELECTION_REQUIRED`
- `AUTH_METHOD_SELECTED`
- `AUTH_SESSION_TIMED_OUT`
- `AUTH_SESSION_BUSY`
- `AUTH_METHOD_SWITCHED`

---

### 14. 现有测试预期仍是旧语义

尤其是：

- `tests/unit/test_run_auth_orchestration_service.py`

当前仍然假设：

- `create_pending_auth()` 直接返回 `PendingAuth`
- auth 流程没有 method selection phase

而现在需要支持：

1. 对多方式 engine/provider：
   - 先返回 method selection
2. 对单一方式 engine/provider：
   - 直接返回 challenge
3. 新增 auth session status API truth
4. 新增 auth session timeout sync

---

## 这轮实际想做的变更

下一轮实现应聚焦于以下闭环：

1. 新增 `server/services/orchestration/run_auth_orchestration_service.py`
2. 更新 `server/models/__init__.py`
3. 更新 `run_interaction_service.py`
4. 更新 `jobs.py`
5. 扩展 `run_store.get_auth_session_status(...)`
6. 调整 `run_job_lifecycle_service.py`
7. 调整 `run_recovery_service.py`
8. 更新 `runtime_event.py` / `factories.py`
9. 更新 `run_observe.html` 与 `e2e_client` 代理接口
10. 更新相关 tests

---

## 推荐的实现顺序

### 第一步：先立住 service

先新增：

- `server/services/orchestration/run_auth_orchestration_service.py`

建议它至少实现这些方法：

1. `create_pending_auth(...)`
   - 返回：
     - `PendingAuthMethodSelection`
     - 或 `PendingAuth`
     - 或 `None`

2. `select_auth_method(...)`
   - 接受用户选中的 method
   - 创建具体 auth session
   - 返回 challenge

3. `submit_auth_input(...)`
   - 接收：
     - `callback_url`
     - `authorization_code`
     - `api_key`
   - 映射到底层：
     - `text`
     - `code`
     - `api_key`

4. `get_auth_session_status(...)`
   - 返回 backend-authored truth

5. `handle_callback_completion(...)`
   - 兼容 `oauth_callback.py`

6. 如有需要：
   - `_available_methods_for(engine, provider_id)`
   - `_map_submission_kind_to_runtime_kind(...)`
   - `_build_pending_auth_from_session_snapshot(...)`
   - `_build_method_selection(...)`

建议在模块级保留这些可 monkeypatch 入口：

- `engine_auth_flow_manager`
- `workspace_manager`
- `concurrency_manager`

避免后续测试 patch 路径继续破裂。

---

### 第二步：把 interaction service 和 jobs route 接上

文件：

- `server/services/orchestration/run_interaction_service.py`
- `server/routers/jobs.py`

要补：

1. `get_pending()` 返回：
   - `pending`
   - `pending_auth_method_selection`
   - `pending_auth`

2. `submit_reply()` 支持：
   - auth method selection
   - auth submission

3. 新增：
   - `GET /v1/jobs/{request_id}/auth/session`

---

### 第三步：扩展 store 的 auth session truth

文件：

- `server/services/orchestration/run_store.py`

重点补：

- `get_auth_session_status(request_id)` 返回完整 truth 视图：
  - `waiting_auth`
  - `phase`
  - `timed_out`
  - `available_methods`
  - `selected_method`
  - `auth_session_id`
  - `challenge_kind`
  - `timeout_sec`
  - `created_at`
  - `expires_at`
  - `server_now`
  - `last_error`

---

### 第四步：再调整编排器

文件：

- `server/services/orchestration/run_job_lifecycle_service.py`
- `server/services/orchestration/run_recovery_service.py`

目标：

1. 高置信度 auth detection 进入 `waiting_auth`
   - 若多方法 -> method selection
   - 若单一方法 -> challenge active

2. recovery 保留：
   - `pending_auth_method_selection`
   - `pending_auth`

---

### 第五步：最后接前端

文件：

- `e2e_client/backend.py`
- `e2e_client/routes.py`
- `e2e_client/templates/run_observe.html`

前端应支持：

1. method selection phase -> `choice` widget
2. challenge active -> `text` widget 或 device_auth 展示
3. submit 错误显式显示
4. auth session 创建后立即拉取 `/api/runs/{id}/auth/session`
5. 断线重连后重新拉取 `/api/runs/{id}/auth/session`

---

## 关键协议约束

### 1. auth method 与 auth submission 必须分层

auth method：

- `callback`
- `device_auth`
- `authorization_code`
- `api_key`

auth submission kind：

- `callback_url`
- `authorization_code`
- `api_key`

### 2. callback 语义固定

`callback` 不是授权码输入。

它表示：

1. 可以自动 callback 完成
2. 也可以手动粘贴 callback URL 完成

### 3. timeout 真相只认 backend

前端不允许把本地计时视为真相。  
唯一真相来源：

- `GET /v1/jobs/{run_id}/auth/session`

---

## 本轮已经核对过的关键文件

以下文件已做过阅读/搜索，下一轮可以直接接续：

- `server/models/interaction.py`
- `server/models/run.py`
- `server/models/runtime_event.py`
- `server/models/__init__.py`
- `server/services/orchestration/run_store.py`
- `server/services/orchestration/run_interaction_service.py`
- `server/services/orchestration/run_job_lifecycle_service.py`
- `server/services/orchestration/run_recovery_service.py`
- `server/services/orchestration/job_orchestrator.py`
- `server/services/engine_management/engine_auth_flow_manager.py`
- `server/engines/codex/auth/runtime_handler.py`
- `server/engines/gemini/auth/runtime_handler.py`
- `server/engines/iflow/auth/runtime_handler.py`
- `server/engines/opencode/auth/runtime_handler.py`
- `server/routers/jobs.py`
- `server/routers/oauth_callback.py`
- `server/runtime/protocol/factories.py`
- `server/runtime/observability/run_observability.py`
- `e2e_client/backend.py`
- `e2e_client/routes.py`
- `e2e_client/templates/run_observe.html`
- `tests/unit/test_run_auth_orchestration_service.py`
- `tests/unit/test_e2e_run_observe_semantics.py`
- `openspec/changes/refine-in-conversation-auth-method-selection-and-session-timeout/design.md`

---

## 建议的下一轮起手命令

建议下一轮直接从以下动作开始：

1. 创建 `server/services/orchestration/run_auth_orchestration_service.py`
2. 更新 `server/models/__init__.py`
3. 更新 `run_interaction_service.py`
4. 更新 `jobs.py`

之后再回到编排和前端。

---

## 当前任务状态

本次任务已按用户要求中止。  
没有执行实现，没有修改业务代码，没有运行测试。  
唯一新增产物是本断点文档。

