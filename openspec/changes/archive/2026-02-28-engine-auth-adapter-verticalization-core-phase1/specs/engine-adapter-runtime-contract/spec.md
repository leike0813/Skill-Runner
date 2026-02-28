## ADDED Requirements

### Requirement: Engine-specific adapter 实现 MUST 按引擎聚合
系统 MUST 将 engine-specific adapter 代码放置在 `server/engines/<engine>/adapter/*`，并通过统一入口装配到执行注册表。

#### Scenario: 注册引擎适配器入口
- **WHEN** 系统初始化 `EngineAdapterRegistry`
- **THEN** 适配器实例来源为 `server/engines/<engine>/adapter` 入口模块
- **AND** 旧 `server/adapters/*` 路径可作为兼容桥接导入

### Requirement: Adapter 组件契约 MUST 标准化
系统 MUST 提供 adapter 组件契约，以约束配置、环境、提示词、命令、解析与会话句柄能力边界。

#### Scenario: 新引擎接入
- **WHEN** 新增一个引擎适配器
- **THEN** 实现方按统一组件契约实现
- **AND** 不需要复制粘贴完整历史 adapter 大类
