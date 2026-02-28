# engine-adapter-runtime-contract Specification

## Purpose
定义执行适配器（adapter）的运行时契约、目录边界与扩展方式，确保引擎差异可管理、可验证、可扩展，同时避免回归到单体大类实现。
## Requirements
### Requirement: Adapter MUST 提供统一运行时命令构建接口
系统 MUST 为所有引擎 Adapter 提供统一的命令构建契约，至少覆盖 start 与 resume 两类执行入口，并允许调用方显式指定是否启用 API 默认 Profile 参数。

#### Scenario: API 链路构建 start 命令
- **WHEN** 后端 API 编排层请求构建某引擎 start 命令且声明启用 Profile
- **THEN** Adapter 返回可执行命令数组并应用该引擎 Profile 默认参数

#### Scenario: Harness 链路构建 start 命令
- **WHEN** Harness 请求构建某引擎 start 命令且声明禁用 Profile
- **THEN** Adapter 返回仅基于透传参数与必要上下文的命令数组

### Requirement: Adapter MUST 提供统一 runtime 流解析接口
系统 MUST 要求所有引擎 Adapter 提供 runtime 流解析接口，输出统一结构字段（parser、confidence、session_id、assistant_messages、raw_rows、diagnostics、structured_types）。

#### Scenario: 引擎流解析返回标准字段
- **WHEN** 任何引擎 Adapter 解析 stdout/stderr/pty 原始字节流
- **THEN** 返回值包含统一结构字段并可直接被协议层消费

### Requirement: Engine-specific adapter 实现 MUST 按引擎聚合
系统 MUST 将 engine-specific adapter 代码放置在 `server/engines/<engine>/adapter/*`，并通过 execution adapter class 装配到执行注册表。

#### Scenario: 注册引擎适配器入口
- **WHEN** 系统初始化 `EngineAdapterRegistry`
- **THEN** 适配器实例来源为 `server/engines/<engine>/adapter/execution_adapter.py` 中的 class
- **AND** MUST NOT 依赖 `entry.py` 工厂或 `build_adapter()` 历史入口

### Requirement: Adapter 组件契约 MUST 标准化
系统 MUST 提供 adapter 组件契约，以约束配置、环境、提示词、命令、解析与会话句柄能力边界。

#### Scenario: 新引擎接入
- **WHEN** 新增一个引擎适配器
- **THEN** 实现方按统一组件契约实现
- **AND** 不需要复制粘贴完整历史 adapter 大类

### Requirement: Legacy 单体 adapter 文件 MUST NOT 存在于运行路径
系统在 commonization 收口后 MUST NOT 依赖或保留旧单体 adapter 路径作为运行实现。

#### Scenario: 旧文件清理
- **WHEN** 扫描适配器实现路径
- **THEN** `server/engines/*/adapter/adapter.py` 不存在
- **AND** `server/adapters/base.py` 不存在

### Requirement: Engine adapter 目录中的旧组件文件 MUST NOT 保留
系统 MUST 将 prompt/session/workspace 的共性实现统一到 runtime common，禁止在每个引擎目录重复保留同类组件文件。

#### Scenario: 目录结构检查
- **WHEN** 扫描 `server/engines/<engine>/adapter/`
- **THEN** 不存在 `entry.py`
- **AND** 不存在 `prompt_builder.py`
- **AND** 不存在 `session_codec.py`
- **AND** 不存在 `workspace_provisioner.py`

### Requirement: Runtime common 组件 MUST 承载引擎无关高重复逻辑
跨引擎高重复逻辑 MUST 位于 `server/runtime/adapter/common/*`，引擎目录仅保留差异实现。

#### Scenario: Prompt/session/workspace 逻辑复用
- **WHEN** 四引擎装配 PromptBuilder/SessionCodec/WorkspaceProvisioner
- **THEN** 共性步骤来自 runtime common
- **AND** 引擎仅通过 profile 与少量差异参数定制

### Requirement: Prompt/Session/Workspace MUST 由 Adapter Profile 驱动
`PromptBuilder`、`SessionHandleCodec`、`WorkspaceProvisioner` MUST 由 profile 驱动的 runtime/common 组件实现。

#### Scenario: 执行适配器初始化
- **WHEN** 任一引擎 execution adapter 初始化
- **THEN** 使用 `ProfiledPromptBuilder`、`ProfiledSessionCodec`、`ProfiledWorkspaceProvisioner`
- **AND** profile 来源为 `server/engines/<engine>/adapter/adapter_profile.json`

### Requirement: Adapter Profile 校验 MUST fail-fast
adapter profile 校验失败 MUST 在 registry 初始化阶段直接报错并阻止服务进入可运行状态。

#### Scenario: profile 非法
- **WHEN** 任一引擎 `adapter_profile.json` 缺失必填字段或枚举非法
- **THEN** `EngineAdapterRegistry` 初始化失败
- **AND** 服务不得进入可运行状态

### Requirement: Adapter Profile MUST 声明引擎执行资产路径
每个引擎 adapter profile MUST 承载配置资产与模型目录元信息，作为执行期单一来源。

#### Scenario: config composer 读取资产
- **WHEN** adapter 构建运行时配置
- **THEN** `bootstrap/default/enforced/schema/skill-defaults` 路径来自 profile 字段
- **AND** composer 不再硬编码 `assets/configs/<engine>/*` 路径

#### Scenario: model registry 读取目录声明
- **WHEN** 系统装配模型目录或 manifest
- **THEN** 静态 manifest 引擎从 profile 的 `model_catalog` 字段读取路径
- **AND** 动态 catalog 引擎从 profile 声明其 seed/cache 与模式元信息

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

### Requirement: Legacy compatibility imports MUST be removed in phase2
phase2 后，adapter/runtime 相关旧路径兼容导入层 MUST NOT 存在。

#### Scenario: Compatibility layer cleanup
- **WHEN** 完成 phase2 收口
- **THEN** 不存在仅用于兼容旧路径的 re-export 模块
- **AND** 全仓引用均指向新目录结构

### Requirement: Trust strategy MUST be adapter-local and centrally dispatched
run folder trust 策略 MUST 以引擎 adapter 层实现，并由 orchestration trust manager 统一调度。

#### Scenario: Adapter-local trust strategy placement
- **WHEN** 为引擎实现 run folder trust
- **THEN** codex 与 gemini 策略分别位于 `server/engines/codex/adapter/trust_folder_strategy.py` 与 `server/engines/gemini/adapter/trust_folder_strategy.py`
- **AND** `server/services/orchestration/run_folder_trust_manager.py` 内部不出现 `if engine == ...` 分支
- **AND** 未注册策略引擎自动使用 registry 内置 noop fallback

### Requirement: Legacy orchestration compatibility shells MUST NOT exist
phase2 收口后，orchestration 目录中的兼容壳文件 MUST 被删除。

#### Scenario: Compatibility shell cleanup
- **WHEN** 完成 phase2 增量收口
- **THEN** 以下文件不存在：
  - `server/services/orchestration/codex_config_manager.py`
  - `server/services/orchestration/config_generator.py`
  - `server/services/orchestration/opencode_model_catalog.py`

