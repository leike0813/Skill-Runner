## ADDED Requirements

### Requirement: Services MUST be domain-organized in phase1
系统 MUST 将 `server/services` 按域分包（orchestration/skill/ui/platform），并停止继续新增扁平 services 模块。

#### Scenario: Service module placement
- **WHEN** 新增服务模块
- **THEN** 模块路径必须位于对应域子包
- **AND** 不允许新增根级 `server/services/*.py` 业务实现文件

### Requirement: Runtime MUST be the only Run Core implementation layer
系统 MUST 将 Run Core 逻辑收敛到 `server/runtime/*`，phase1 不允许新增 `server/services/run/*`。

#### Scenario: Run core placement
- **WHEN** 实现运行时协议、状态机、事件物化与运行观测能力
- **THEN** 代码必须位于 `server/runtime/*`
- **AND** `server/services` 仅允许 façade/兼容导入层

### Requirement: Runtime adapter common MUST NOT depend on flat services modules
`server/runtime/adapter/common/*` MUST 不再直接依赖扁平 services 模块。

#### Scenario: Adapter common imports
- **WHEN** 检查 `server/runtime/adapter/common/*` import
- **THEN** 不出现 `server.services.<flat_module>` 引用
