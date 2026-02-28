## ADDED Requirements

### Requirement: Runtime auth core MUST be engine-agnostic
`server/runtime/auth/**` MUST 不直接依赖 `server/engines/**`，并且 MUST 不包含 engine 名称业务分支。

#### Scenario: runtime auth static guard
- **WHEN** 运行 runtime auth 静态守卫测试
- **THEN** 不存在 `server/engines` 导入
- **AND** 不存在 `if engine ==` / `if engine in (...)` 分支

### Requirement: Shared auth protocol modules MUST live under engines/common
跨引擎复用的鉴权协议代码（如 OpenAI 协议）MUST 位于 `server/engines/common/**`，而非 runtime 目录。

#### Scenario: OpenAI shared protocol import
- **WHEN** CodeX 与 OpenCode 复用 OpenAI OAuth/device 协议
- **THEN** 通过 `server/engines/common/openai_auth/*` 导入
- **AND** `server/runtime/auth/**` 不承载该共享协议实现

### Requirement: Engine auth behavior MUST be provided through engine runtime handlers
每个引擎 MUST 通过 `server/engines/<engine>/auth/runtime_handler.py` 提供 start/refresh/input/callback/finalize/terminate/trust 能力。

#### Scenario: start flow delegation
- **WHEN** `EngineAuthFlowManager.start_session` 被调用
- **THEN** runtime planner/starter 通过 engine handler 委托具体实现
- **AND** manager 不直接实现引擎启动分支

### Requirement: Runtime callback completion MUST be channel-based only
`server/runtime/auth/session_callback_completer.py` MUST 仅提供 `complete_callback(channel, state, code, error)` 统一入口，MUST NOT 暴露按引擎命名的 completion API。

#### Scenario: callback completion entry
- **WHEN** callback 请求进入 runtime auth completer
- **THEN** 统一按 `channel` 进行 state 消费与会话定位
- **AND** 具体 token exchange/credential write 由 engine handler `complete_callback` 承担

## CHANGED Requirements

### Requirement: EngineAuthFlowManager is a facade-only coordinator
`EngineAuthFlowManager` SHOULD 仅保留编排与兼容层职责，不承载 engine-specific 会话业务逻辑。

#### Scenario: cancel flow
- **WHEN** 调用 cancel
- **THEN** manager 通过 handler `terminate_session` 处理引擎终止逻辑
- **AND** manager 负责统一会话终态与锁释放
