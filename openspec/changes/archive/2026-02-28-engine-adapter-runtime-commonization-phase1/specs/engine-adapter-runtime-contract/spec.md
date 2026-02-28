## ADDED Requirements

### Requirement: Adapter Runtime Must Not Depend on Legacy Monolith
`server/engines/*/adapter/adapter.py` 与 `server/adapters/base.py` 在 phase1 后 MUST NOT 存在。

#### Scenario: Legacy adapter files removed
- **GIVEN** 代码库完成本 change
- **WHEN** 扫描 `server/engines/*/adapter/adapter.py` 与 `server/adapters/base.py`
- **THEN** 这些文件不存在

### Requirement: Engine Adapter Registry Uses Execution Adapter Only
`server/services/engine_adapter_registry.py` MUST 只使用 execution adapter class，不得依赖旧工厂入口。

#### Scenario: Registry initialization
- **GIVEN** 服务启动
- **WHEN** 初始化 engine adapter registry
- **THEN** 不调用任何 `build_adapter()` 入口

### Requirement: Engine Adapter Registry Must Not Use Entry Factory
registry MUST 直接导入并实例化 `server/engines/*/adapter/execution_adapter.py` 中的类，不得依赖包级 `entry.py` 工厂。

#### Scenario: Registry direct instantiation
- **GIVEN** 服务启动并初始化 adapter registry
- **WHEN** 加载四个引擎 adapter
- **THEN** 导入来源是 execution adapter class
- **AND** `server/engines/*/adapter/entry.py` 不参与执行路径

### Requirement: Runtime Common Components Host Engine-Agnostic Logic
跨引擎高重复逻辑 MUST 位于 `server/runtime/adapter/common/*`，引擎目录仅保留差异实现。

#### Scenario: Prompt/session/workspace shared flow
- **GIVEN** 四引擎 adapter 组件
- **WHEN** 执行 prompt/session/workspace 逻辑
- **THEN** 共性步骤来自 runtime common，差异步骤由 engine-specific 组件补充

### Requirement: Prompt/Session/Workspace Must Be Profile-Driven
`PromptBuilder`、`SessionHandleCodec`、`WorkspaceProvisioner` MUST 由 runtime/common 的 profile 驱动组件实现，不得在引擎目录重复实现同类逻辑。

#### Scenario: Engine adapter profile injection
- **GIVEN** 任一 engine execution adapter 初始化
- **WHEN** 装配 prompt/session/workspace 组件
- **THEN** 使用 `ProfiledPromptBuilder`、`ProfiledSessionCodec`、`ProfiledWorkspaceProvisioner`
- **AND** profile 来源为 `server/engines/<engine>/adapter/adapter_profile.json`

### Requirement: Adapter Profiles Must Validate Fail-Fast
adapter profile 校验失败 MUST 在初始化阶段报错并阻止服务进入可运行状态。

#### Scenario: Invalid profile blocks startup
- **GIVEN** 某引擎 `adapter_profile.json` 缺失必填字段或枚举非法
- **WHEN** 初始化 `EngineAdapterRegistry`
- **THEN** 抛出配置错误并终止初始化流程

### Requirement: Engine Adapter Legacy Component Files Must Not Exist
以下文件在 phase1 收口后 MUST NOT 存在：
1. `server/engines/*/adapter/entry.py`
2. `server/engines/*/adapter/prompt_builder.py`
3. `server/engines/*/adapter/session_codec.py`
4. `server/engines/*/adapter/workspace_provisioner.py`

#### Scenario: Legacy component files removed
- **GIVEN** 代码库完成本 change
- **WHEN** 扫描上述路径模式
- **THEN** 无匹配文件存在
