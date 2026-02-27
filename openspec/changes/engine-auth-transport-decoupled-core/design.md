## Context

当前 `EngineAuthFlowManager` 集成了：
1. transport 分发；
2. 各引擎编排状态机；
3. CLI/协议执行；
4. 会话生命周期与日志管理。

这导致单文件复杂度过高，且 transport 与 engine 逻辑相互渗透。

## Target Architecture

### 1) Runtime Layers

新增 `server/services/auth_runtime/`：

1. `orchestrators/oauth_proxy_orchestrator.py`
   - 仅处理 `oauth_proxy` 状态机与编排。
2. `orchestrators/cli_delegate_orchestrator.py`
   - 仅处理 `cli_delegate` 状态机与编排。
3. `drivers/base.py`
   - 定义 `OAuthProxyDriver` 与 `CliDelegateDriver` 协议。
4. `driver_registry.py`
   - 维护 `(engine, provider_id, auth_method, transport) -> driver` 映射。
5. `session_store.py`
   - 统一持久化/内存态会话存取和状态快照。
6. `log_writer.py`
   - 统一写 `events.jsonl` 和 transport 特有日志文件。

### 2) EngineAuthFlowManager as Facade

`EngineAuthFlowManager` 退化为 façade：
1. 对新 API 转发到相应 orchestrator；
2. 对旧 API 做兼容转换（映射到新模型）；
3. 聚合查询当前活动会话（用于 UI 顶部态显示）。

### 3) State Machines

#### oauth_proxy

1. `starting`
2. `waiting_user`
3. `code_submitted_waiting_result`（仅 fallback 输入）
4. `polling_result`（仅 device-auth）
5. `succeeded|failed|canceled|expired`

约束：
1. 禁止 `waiting_orchestrator`。

#### cli_delegate

1. `starting`
2. `waiting_orchestrator`
3. `waiting_user`
4. `code_submitted_waiting_result`
5. `succeeded|failed|canceled|expired`

约束：
1. 禁止 `polling_result`。

### 4) API Design

新增 V2 transport 分组接口：
1. `POST /v1/engines/auth/oauth-proxy/sessions`
2. `GET /v1/engines/auth/oauth-proxy/sessions/{id}`
3. `POST /v1/engines/auth/oauth-proxy/sessions/{id}/input`
4. `POST /v1/engines/auth/oauth-proxy/sessions/{id}/cancel`
5. `GET /v1/engines/auth/oauth-proxy/callback/openai`
6. `POST /v1/engines/auth/cli-delegate/sessions`
7. `GET /v1/engines/auth/cli-delegate/sessions/{id}`
8. `POST /v1/engines/auth/cli-delegate/sessions/{id}/input`
9. `POST /v1/engines/auth/cli-delegate/sessions/{id}/cancel`

旧接口：
1. `/v1/engines/auth/sessions*` 保持兼容，响应增加 `deprecated=true`（过渡期）。

### 5) Session Model V2

新增模型：
1. `AuthSessionStartRequestV2`
   - `transport` 必填
   - `method` 移除
   - `auth_method` + `provider_id` 表达鉴权类型
2. `AuthSessionSnapshotV2`
   - 新增 `transport_state_machine`
   - 新增 `orchestrator`
   - 新增 `log_root`
3. `AuthSessionInputRequestV2`
   - 保持 `kind/value`

### 6) Logging Model

统一路径：
1. `data/engine_auth_sessions/oauth_proxy/<session_id>/events.jsonl`
2. `data/engine_auth_sessions/oauth_proxy/<session_id>/http_trace.log`
3. `data/engine_auth_sessions/cli_delegate/<session_id>/events.jsonl`
4. `data/engine_auth_sessions/cli_delegate/<session_id>/pty.log`
5. `data/engine_auth_sessions/cli_delegate/<session_id>/stdin.log`

`events.jsonl` 统一事件：
1. `session_started`
2. `state_changed`
3. `input_received`
4. `callback_received`
5. `driver_error`
6. `session_finished`

### 7) Driver Registration Strategy

初始迁移 driver：
1. `codex`：oauth/browser、oauth/device、cli/browser、cli/device
2. `opencode+openai`：同上
3. `gemini`：cli_delegate
4. `iflow`：cli_delegate
5. `opencode` 其他 provider：cli_delegate / api_key

## Rollout Strategy

1. 先引入新层并迁移 `oauth_proxy`（codex + opencode/openai）。
2. 再迁移 `cli_delegate` 族群。
3. UI 切换到 V2 路由。
4. 旧路由兼容期结束后在后续 change 删除。

## Failure Modes

1. 组合未注册：返回 `422`。
2. driver 运行异常：写 `driver_error` 并进入 `failed`。
3. device-auth 轮询失败：进入 `failed`，不降级其他 transport。
4. callback state 非法：`400`，并写审计事件。
5. 会话冲突：`409`（保留 interaction gate 语义）。
