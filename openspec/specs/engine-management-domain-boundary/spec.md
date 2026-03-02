# engine-management-domain-boundary Specification

## Purpose
TBD - created by archiving change refactor-engine-management-domain. Update Purpose after archive.
## Requirements
### Requirement: Engine management modules MUST reside in dedicated domain package
系统 MUST 将 engine 管理域实现收敛到 `server/services/engine_management`，不再放置于 `server/services/orchestration`。

#### Scenario: module placement
- **WHEN** 扫描 engine 管理域模块
- **THEN** `agent_cli_manager/engine_adapter_registry/engine_auth_bootstrap/engine_auth_flow_manager/engine_command_profile/engine_interaction_gate/engine_policy/engine_upgrade_manager/engine_upgrade_store/model_registry/runtime_profile` MUST 位于 `server/services/engine_management/*`
- **AND** `server/services/orchestration/` 中不存在上述模块实现文件

### Requirement: Runtime/service/router/engine imports MUST switch to new package
系统 MUST 一次性完成对迁移模块的全仓依赖切换。

#### Scenario: import path migration complete
- **WHEN** 检查 `server/` 与 `tests/` 的 import
- **THEN** 不存在 `server.services.orchestration.<migrated_module>` 的引用
- **AND** 所有调用方改为 `server.services.engine_management.<migrated_module>`

#### Scenario: Runtime observability respects orchestration boundary
- **WHEN** runtime observability needs a job-control protocol
- **THEN** it MUST depend on a runtime-neutral/shared port definition
- **AND** `server/runtime/*` MUST NOT import `server.services.orchestration.*`

### Requirement: No orchestration compatibility shells MUST remain
本次迁移 MUST 不引入或保留 orchestration 兼容壳（re-export/alias shell）。

#### Scenario: compatibility shell forbidden
- **WHEN** 扫描 `server/services/orchestration`
- **THEN** 不存在仅用于兼容旧路径的 `<migrated_module>.py`
- **AND** 不存在 `from server.services.engine_management...` 的旧路径包装壳文件

### Requirement: Auth/upgrade/model-policy/runtime-profile behavior MUST remain backward compatible
目录重构 MUST 不改变 engine 管理能力的运行语义。

#### Scenario: auth session lifecycle unchanged
- **WHEN** 客户端调用 engine auth start/input/cancel/callback
- **THEN** 会话状态、错误码与返回字段语义保持兼容

#### Scenario: engine upgrade flow unchanged
- **WHEN** 客户端创建并查询 engine 升级任务
- **THEN** 任务并发约束、状态流转与 per-engine stdout/stderr 语义保持兼容

#### Scenario: model/policy/runtime profile unchanged
- **WHEN** 读取模型清单、执行 skill engine policy 校验、解析 runtime profile
- **THEN** 有效引擎集合、模型解析结果与环境变量组装语义保持兼容

### Requirement: Docs and tests MUST reflect ownership boundary
文档与测试 MUST 同步新目录归属，避免路径漂移。

#### Scenario: docs synchronized
- **WHEN** 检查核心组件与项目结构文档
- **THEN** engine 管理域路径描述更新为 `server/services/engine_management/*`

#### Scenario: tests synchronized
- **WHEN** 运行 engine 管理相关单测与路由回归
- **THEN** import/monkeypatch/路径断言均基于新路径并通过测试
