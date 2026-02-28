## Why

当前 auth 重构仍存在“runtime 服务抽象已落地，但 manager 与 runtime 仍残留部分引擎耦合”的问题。  
为避免后续继续漂移，本 change 将 auth 核心推进到严格边界：

1. `server/runtime/auth/**` 彻底 engine-agnostic。
2. engine-specific 鉴权分支、终态收口、回滚与终止逻辑全部下沉到 `server/engines/<engine>/auth/**`。
3. 对外 `/v1` 与 `/ui` 鉴权接口保持兼容，重构仅发生在内部实现层。
4. 跨引擎共享协议（如 CodeX/OpenCode 共用 OpenAI 协议）放在 `server/engines/common/**`，不放在 runtime。

## What Changes

1. 以 `EngineAuthRuntimeHandler` 作为 runtime 扩展单元，统一承接 `plan/start/refresh/input/callback` 及 finalize/terminate/trust 策略。
2. `EngineAuthFlowManager` 收敛为 façade：锁、会话存储、transport 编排、API 兼容，不再直接承载 engine-specific 终态清理分支。
3. `runtime/auth` 服务通过 handler registry 调度，不直接 import `server/engines/**`。
4. 增加静态守卫测试，禁止 `runtime/auth` 引入 engine-specific 依赖与 `if engine ==` 分支。
5. 补齐开发者文档，明确 capability/driver 接入顺序与扩展点。

## Scope

### In Scope

1. `server/runtime/auth/*`、`server/services/engine_auth_flow_manager.py`、`server/engines/*/auth/runtime_handler.py` 的重构。
2. OpenSpec 约束补齐与本 change artifacts。
3. auth 关键测试、静态守卫测试与文档同步。

### Out of Scope

1. 不新增 provider 或 transport。
2. 不修改对外 API 路径与请求语义。
3. 不改动 adapter 执行协议。

## Success Criteria

1. `server/runtime/auth/**` 无 `server/engines/**` 依赖、无 engine 名称分支。
2. manager 不再直接做引擎终态回滚/监听清理分支，改为 handler hook。
3. 四引擎鉴权回归通过（oauth_proxy/cli_delegate 既有行为不回归）。
4. OpenSpec 与实现一致，`openspec validate` 通过。
