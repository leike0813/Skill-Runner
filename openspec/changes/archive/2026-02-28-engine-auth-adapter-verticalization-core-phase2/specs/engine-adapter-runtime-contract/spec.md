## ADDED Requirements

### Requirement: Engine adapter MUST be implemented under engine vertical package
系统 MUST 将四个引擎的 adapter 主实现放置在 `server/engines/<engine>/adapter/adapter.py`，并由 `entry.py` 统一装配。

#### Scenario: Registry loads adapter from engine package
- **WHEN** `EngineAdapterRegistry` 初始化
- **THEN** 每个引擎的适配器来自 `server/engines/<engine>/adapter` 入口
- **AND** 不再依赖 `server/adapters/{engine}_adapter.py` 旧实现文件

### Requirement: Adapter extension MUST follow six-component contract
新增引擎或重构现有引擎时 MUST 实现组件接口（配置、工作区、提示词、命令、解析、会话句柄），并通过 `EngineExecutionAdapter` 编排。

#### Scenario: New engine onboarding
- **WHEN** 开发者新增引擎适配器
- **THEN** 必须提供 6 组件实现并在 `entry.py` 完成装配
- **AND** 不允许复制旧单体 adapter 大类作为唯一实现方式

## MODIFIED Requirements

### Requirement: Legacy adapter files are removed from runtime path
系统在 phase2 后 MUST 移除 `server/adapters/{codex,gemini,iflow,opencode}_adapter.py` 作为运行实现路径。

#### Scenario: Import legacy adapter module
- **WHEN** 代码尝试导入旧 adapter 文件
- **THEN** 该导入路径不再作为主实现来源
- **AND** 运行逻辑已由 `server/engines/*/adapter` 提供
