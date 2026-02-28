## Design Overview

本 change 是 auth 侧专项重构收口，保持外部契约不变，只重构内部分层。

### 1) Auth Runtime 服务分层

`server/runtime/auth/` 固化为以下分层：

1. `session_start_planner.py`
   - 归一化 start 参数，校验 `(transport, engine, auth_method, provider_id)` 组合。
   - 决定是否需要 CLI 命令及命令可用性。
2. `session_starter.py`（本 change 新增）
   - 承接 `start_session` 的 engine-specific 创建逻辑。
   - 负责 listener 启停、trust 注册、会话对象创建、事件写入、失败回滚。
3. `session_refresher.py`
   - driver 维度状态推进（refresh）。
4. `session_input_handler.py`
   - `input(kind/value)` 分发与收口。
5. `session_callback_completer.py`
   - callback state 校验/消费、token exchange、终态收口。

### 2) Manager Façade 目标

`EngineAuthFlowManager` 保持：

1. 路由兼容入口。
2. 全局锁与 interaction gate 管理。
3. 会话存储与快照转换。
4. 对 runtime 服务的编排调用。

`EngineAuthFlowManager` 不再承担：

1. engine-specific 启动分支。
2. callback/input/refresh 的核心业务流程。

### 3) Engine-specific 边界

1. engine-specific auth 实现在 `server/engines/<engine>/auth/*`。
2. runtime 服务通过 manager 引用这些 flow/driver，不在 runtime 层硬编码协议常量分散到外层调用点。

### 4) 状态机与兼容性

1. 状态机语义保持不变：
   - `oauth_proxy` 禁止 `waiting_orchestrator`
   - `cli_delegate` 允许 `waiting_orchestrator`
2. 对外端点保持不变：
   - `/v1/engines/auth/oauth-proxy/sessions*`
   - `/v1/engines/auth/cli-delegate/sessions*`
   - `/v1/engines/auth/sessions*`（兼容层）
   - `/ui/engines/auth/*`

### 5) 风险与控制

1. 风险：start 分支迁移造成行为漂移。
   - 控制：新增 starter 直测 + 复跑 manager/routes 回归。
2. 风险：异常回滚漏释放全局锁。
   - 控制：覆盖 cancel/异常启动/回滚路径。
3. 风险：spec 与代码再次偏移。
   - 控制：tasks 记录已完成基线并在同 change 内标注。
