## ADDED Requirements

### Requirement: Runtime modules MUST not directly import orchestration singletons
`server/runtime/**` MUST 通过 contracts/ports 与 orchestration 协作，不得直接依赖 `server/services/orchestration/*`。

#### Scenario: Runtime boundary guard
- **WHEN** 检查 runtime 模块依赖
- **THEN** 不存在 `from server.services.orchestration...` 或等价直接导入
- **AND** runtime 仅依赖 runtime contracts 与注入端口

### Requirement: Runtime execution business modules MUST live in orchestration
`run_execution_core` 与 `run_interaction_service` 作为业务编排模块 MUST 位于 `services/orchestration`。

#### Scenario: Execution module ownership
- **WHEN** 扫描运行执行核心模块
- **THEN** `server/runtime/execution/` 下不再存在上述业务实现文件
- **AND** 等价实现位于 `server/services/orchestration/`
