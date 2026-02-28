## ADDED Requirements

### Requirement: Auth engine-specific logic MUST stay inside engine auth packages
系统 MUST 将 engine-specific 鉴权逻辑限定在 `server/engines/<engine>/auth/*`，避免回流到 manager。

#### Scenario: manager 不直接承载 engine-specific start 分支
- **WHEN** 代码执行 `start_session(...)`
- **THEN** manager 不应包含引擎启动分支实现
- **AND** 具体分支由 runtime service 调用 engine auth flow 对象完成

### Requirement: Runtime auth services MUST define stable extension points
系统 MUST 提供稳定的 auth runtime 扩展点，以支持新引擎低成本接入。

#### Scenario: 标准 runtime 服务链可复用
- **WHEN** 新引擎接入 auth 能力
- **THEN** 通过 `planner/starter/refresher/input/callback` 扩展点接入
- **AND** 不需要在 manager 新增 engine-specific 分支

### Requirement: Runtime auth core MUST stay engine-agnostic
`server/runtime/auth/**` MUST 不包含 engine-specific 引用与分支；engine-specific 鉴权逻辑 MUST 下沉到 `server/engines/<engine>/auth/**`。

#### Scenario: Runtime auth implementation references
- **WHEN** 实现 `start/refresh/input/callback` runtime 服务
- **THEN** 不允许直接依赖 `server/engines/**`
- **AND** 不允许在 runtime 层出现 `if engine == ...` 的业务分支
- **AND** 本约束由后续 `engine-auth-runtime-modularization-phase2` 变更落地为代码硬门禁
