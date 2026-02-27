## Context

当前 auth 体系已支持 transport 分组（`oauth_proxy` / `cli_delegate`），但 `iflow` 仅在 `cli_delegate` 下可用。  
本次扩展在不回归现有路径的前提下，为 `iflow` 增加协议代理能力，保持与 `gemini` 的双模式思路一致：

- `callback`：自动本地回调优先，允许 `/input` 兜底；
- `auth_code_or_url`：纯手工输入。

## Design Decisions

1. **零 CLI 原则（oauth_proxy）**  
   `iflow + oauth_proxy` 禁止启动 `iflow` CLI 进程，仅走协议请求。

2. **双模式并列，不自动切换**  
   测试阶段在管理 UI 显式提供两按钮，不做环境自动判定。

3. **状态机约束**  
   `oauth_proxy` 会话只允许：
   `starting -> waiting_user -> code_submitted_waiting_result(可选) -> succeeded|failed|canceled|expired`  
   严禁 `waiting_orchestrator`。

4. **写盘兼容优先**  
   成功后按现有 `auth-status` 约束写盘：
   - `.iflow/oauth_creds.json`
   - `.iflow/iflow_accounts.json`
   - `.iflow/settings.json`

5. **回调失败不阻断会话（callback 模式）**  
   若本地 listener 启动失败，会话仍进入 `waiting_user`，由用户 `/input` 兜底。

## Architecture

### 1) 新增 `iflow_oauth_proxy_flow.py`

职责：

1. 构造 authorize URL（`https://iflow.cn/oauth`）；
2. 维护 `state`、解析输入（URL/code）；
3. 调用 token endpoint（`https://iflow.cn/oauth/token`）；
4. 拉取 user-info（`https://iflow.cn/api/oauth/getUserInfo`）；
5. 原子写盘 iFlow 认证文件。

### 2) 新增 `iflow_local_callback_server.py`

职责：

1. 本地监听 `/oauth2callback`（默认 `127.0.0.1:11451`）；
2. 将 `state/code/error` 回调给 `engine_auth_flow_manager.complete_iflow_callback`；
3. 返回成功/失败 HTML；
4. 生命周期与会话绑定，不后台常驻。

### 3) manager 接入

`engine_auth_flow_manager.py` 新增：

1. driver 注册（`oauth_proxy + iflow + callback|auth_code_or_url`）；
2. callback state 索引与一次性消费；
3. iflow oauth_proxy start/refresh/input/callback/finalize 全链路；
4. iflow listener 的启动/停止；
5. 与现有 `iflow cli_delegate` 并存。

### 4) orchestrator 与 UI

1. `oauth_proxy_orchestrator` 放行 `engine=iflow`；
2. 管理 UI 新增两个 iFlow OAuth 代理按钮；
3. 输入提示在 iFlow 下明确“授权码或回调 URL”。

## Failure Handling

1. listener 不可用：保持 `waiting_user`，允许手工输入；
2. state 不匹配/重复消费：`failed`；
3. token/user-info 请求失败：`failed` 并保留错误摘要；
4. 会话过期：`expired`；
5. 取消会话：释放全局锁与 listener。

## Observability

建议审计字段：

1. `local_callback_listener_started`
2. `manual_fallback_used`
3. `oauth_callback_received`
4. `callback_mode`（`auto`/`manual`）

## Security

1. 不记录明文 code/token 到事件日志；
2. callback state 一次性消费；
3. 回调 listener 仅在会话存活期间开放。
