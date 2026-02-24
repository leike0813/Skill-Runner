## Why

当前 interactive 运行时同时保留了历史 `resumable/sticky_process` 双档位语义，导致状态分支和恢复路径复杂、重复且容易漂移。

近期验证显示目标后端引擎均可恢复，因此继续保留 sticky 专属分支只会增加维护成本。

需要一次收敛改造：

- 统一为单一可恢复会话范式；
- 将 `auto` 明确建模为 `interactive` 状态机的受限子集；
- 产出 Session Statechart SSOT 并以实现侧状态机表约束分支；
- 清理对外接口中的 legacy 字段与错误码；
- 通过单一 OpenSpec change 完整追溯设计、规范和实现。

## What Changes

1. 运行时语义收敛
- 移除 `resumable/sticky_process` 双档位分叉，统一可恢复路径。
- `strict=true`：等待用户回复，不因会话超时自动失败。
- `strict=false`：超时触发自动决策并通过统一 resume 路径继续。

2. 对外接口收敛
- 移除 `interactive_profile.kind` 暴露。
- 移除 `INTERACTION_WAIT_TIMEOUT` / `INTERACTION_PROCESS_LOST` 错误码。
- 保持 `execution_mode`、`pending_interaction`、`interaction history` 契约不变。

3. 状态机 SSOT
- 新增 `docs/session_runtime_statechart_ssot.md`（三层状态图 + 旧名映射附录）。
- 新增 `server/services/session_statechart.py` 作为 canonical 状态/事件/守卫/动作锚点。

4. 存储与迁移
- 一次性 SQLite 迁移重建 `request_interactive_runtime`。
- 删除 sticky 专属字段：`profile_json`、`wait_deadline_at`、`process_binding_json`。

5. 测试与约束
- 改造 interactive 单测，删除 sticky 分支断言。
- 新增状态机契约测试与协议对齐测试，防止后续实现漂移。

## Naming

变更命名：`2026-02-23-interactive-44-single-resumable-session-statechart-ssot`

## Capabilities

### Modified Capabilities
- `interactive-session-resume`
- `interactive-run-lifecycle`
- `interactive-run-restart-recovery`
- `interactive-session-timeout-unification`
- `interactive-job-api`
- `interactive-decision-policy`

### Added Capabilities
- `session-runtime-statechart-ssot`

## Impact

- 代码：
  - `server/models.py`
  - `server/services/agent_cli_manager.py`
  - `server/services/job_orchestrator.py`
  - `server/services/run_interaction_service.py`
  - `server/services/run_store.py`
  - `server/services/session_statechart.py`
- 文档：
  - `docs/session_runtime_statechart_ssot.md`
  - `docs/api_reference.md`
  - `docs/dev_guide.md`
  - `docs/runtime_stream_protocol.md`

## Follow-up Changes

- `2026-02-24-interactive-45-fcmp-single-stream-event-architecture`（事件流单流化与 FCMP 协议收敛）
