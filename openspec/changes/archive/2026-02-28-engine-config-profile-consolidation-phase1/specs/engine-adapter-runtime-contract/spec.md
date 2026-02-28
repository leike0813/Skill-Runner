## MODIFIED Requirements

### Requirement: Adapter Profile MUST Be the Single Source for Engine Execution Assets
系统 MUST 要求每个引擎的 adapter profile 承载其执行资产路径（bootstrap/default/enforced/schema/skill-defaults）与模型目录元信息。

#### Scenario: Composer reads config asset paths from profile
- **GIVEN** 任一引擎 execution adapter 已加载 profile
- **WHEN** `config_composer` 构建运行时配置
- **THEN** default/enforced/bootstrap 等路径来自 profile 字段
- **AND** composer 不再硬编码 `assets/configs/<engine>/*` 路径

#### Scenario: Invalid profile blocks adapter startup
- **GIVEN** adapter profile 缺失 `config_assets` 或字段非法
- **WHEN** 初始化 `EngineAdapterRegistry`
- **THEN** 系统 MUST fail-fast 抛错并阻止服务进入可运行状态

### Requirement: Runtime Adapter Core MUST Stay Engine-Agnostic While Consuming Profiles
runtime adapter core MUST 通过统一 profile 接口消费引擎差异，禁止在 runtime/core 层引入新的引擎路径硬编码。

#### Scenario: Profile-driven execution wiring
- **GIVEN** runtime/common 组件与 execution adapter 装配
- **WHEN** 读取引擎资产路径
- **THEN** 统一通过 `AdapterProfile` 字段访问
- **AND** 不增加新的 `if engine == ...` 路径分支
