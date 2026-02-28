## Design Overview

本 change 只做 auth 侧架构收口，核心原则是：

1. runtime 只做 transport orchestration 与通用会话生命周期。
2. engine-specific 鉴权行为（start 细节、刷新、输入、回调、回滚、终止）全部在 engine handler 中实现。
3. manager 保留 façade 能力，不再持有引擎分支逻辑。
4. 共享协议能力（跨引擎复用）放在 `server/engines/common/**`，而不是 runtime 目录。

## 1) Runtime/Auth 分层

### Runtime 层（engine-agnostic）

1. `session_lifecycle.py`：承载 session 相关统一编排组件：
   - `AuthSessionStartPlanner`
   - `AuthSessionStarter`
   - `AuthSessionRefresher`
   - `AuthSessionInputHandler`
   - `AuthSessionCallbackCompleter`
2. `session_lifecycle.py` 中各组件分别负责：
   - start 计划规范化并委托 handler `plan_start`
   - start 上下文构建/日志初始化/trust 注入与异常回滚
   - refresh 循环与终态收口
   - input 校验与委托 handler `handle_input`
   - callback state 消费与委托 handler `complete_callback`
3. callback completer 对外仅暴露 channel-based 统一入口，不提供 `complete_<engine>_callback` 命名方法。
4. `callbacks.py`：统一承载 callback 相关通用能力（router/state_store/listener_registry），减少同 scope 代码分散。

### Common 层（跨引擎共享协议）

1. `server/engines/common/openai_auth/*`：承载 CodeX/OpenCode 共用的 OpenAI OAuth/device 协议入口。
2. runtime 只调用引擎 handler；共享协议由引擎 handler 或引擎协议模块自行引用。

### Engine 层（engine-specific）

每个引擎在 `server/engines/<engine>/auth/runtime_handler.py` 提供：

1. `plan_start(...)`
2. `start_session_locked(...)`
3. `refresh_session_locked(...)`
4. `handle_input(...)`
5. `complete_callback(...)`
6. `cleanup_start_error(...)`
7. `on_session_finalizing(...)`（终态回滚/监听停止/state 清理）
8. `terminate_session(...)`（CLI/PTY 终止）
9. `requires_parent_trust_bootstrap()`（trust 注入策略）

## 2) Manager 收口策略

`EngineAuthFlowManager` 仅保留：

1. driver matrix 注册与 transport method 解析。
2. 全局锁与 active session 仲裁。
3. session store/log store/event append。
4. runtime 服务编排与 façade API（start/get/input/cancel/callback）。
   - callback façade 仅保留 `complete_callback(channel, state, code, error)` 统一入口；引擎特化由 handler 负责。

下沉到 engine handler：

1. listener 启停。
2. callback state 清理。
3. provider-specific rollback（如 opencode google antigravity）。
4. CLI delegate 进程终止策略。

## 3) 兼容性

1. 对外 API 不变：
   - `/v1/engines/auth/oauth-proxy/sessions*`
   - `/v1/engines/auth/cli-delegate/sessions*`
   - `/v1/engines/auth/sessions*`（兼容层）
   - `/ui/engines/auth/*`
2. 会话字段不删减，仅内部实现调整。

## 4) 静态守卫

新增测试硬门禁：

1. `server/runtime/auth/**/*.py` 不允许出现 `server/engines` 导入。
2. `server/runtime/auth/**/*.py` 不允许出现 `if engine ==` 或 `if engine in (...)` 业务分支。

## 5) 风险与控制

1. 风险：下沉后回调/终态清理遗漏。
   - 控制：`test_engine_auth_flow_manager.py` 全量回归。
2. 风险：迁移后锁未释放。
   - 控制：cancel/failed/expired 路径回归。
3. 风险：handler 接口扩展导致接线错误。
   - 控制：`test_engine_auth_driver_contracts.py` + 新静态守卫测试。
