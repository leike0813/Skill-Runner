# engine-runtime-config-layering Specification

## Purpose
定义运行时配置的统一分层优先级（bootstrap/engine_default/skill_default/runtime_override/enforced）和 adapter profile 驱动的路径解析。
## Requirements
### Requirement: 运行时配置组装 MUST 采用统一分层优先级

系统 MUST 为 `codex/gemini/iflow/opencode/qwen` 采用统一配置组装顺序：`engine_default -> skill defaults -> runtime overrides -> enforced`。

#### Scenario: effective effort is written into engine-specific runtime config
- **WHEN** 所选模型支持 effort 且请求包含 `effort`（或默认值）
- **THEN** 系统 MUST 在 run-dir 配置写入阶段注入该引擎实际生效的 effort 值
- **AND** 写入值 MUST 是真实生效值，而不是字面 `"default"`

#### Scenario: unsupported effort remains a no-op
- **WHEN** 所选模型不支持 effort
- **THEN** 系统 MUST NOT 写入无效的 effort 配置
- **AND** 即使客户端提交了 `effort` 也不应改变运行行为

### Requirement: bootstrap 与 engine_default MUST 职责分离
系统 MUST 将 bootstrap 与 engine_default 视为不同职责层：bootstrap 用于初始化基线，engine_default 用于运行时组装基底。

#### Scenario: 首次初始化 agent_home
- **WHEN** 系统执行 layout/bootstrap 过程
- **THEN** 写入 bootstrap 文件用于鉴权与基础可用性初始化
- **AND** 不要求 bootstrap 承担运行时策略覆盖职责

#### Scenario: 运行一次执行任务
- **WHEN** 系统构建引擎运行时配置
- **THEN** 运行时配置 MUST 从 `engine_default` 起算
- **AND** 再按统一优先级合并 skill/runtime/enforced

### Requirement: Runtime Config Layering MUST 通过 Adapter Profile 解析资产路径
系统在执行 `engine_default -> skill defaults -> runtime overrides -> enforced` 分层组装时，MUST 从 adapter profile 解析各层资产路径。

#### Scenario: 分层文件路径来自 profile
- **WHEN** 任一引擎执行配置分层组装
- **THEN** `default/enforced/skill-defaults` 路径来自该引擎 `adapter_profile.json`
- **AND** 不依赖公共配置中心中的引擎专属路径键

### Requirement: Bootstrap 路径归属 MUST 迁移到 Adapter Profile
bootstrap 配置文件路径 MUST 由 adapter profile 声明，以实现引擎资产归档与审计一致性。

#### Scenario: 初始化读取 bootstrap 路径
- **WHEN** agent layout/bootstrap 逻辑读取引擎 bootstrap 配置
- **THEN** 路径来自 adapter profile 的 `config_assets.bootstrap_path`
- **AND** 引擎迁移/重命名无需修改公共配置中心

### Requirement: 模型目录与 Manifest 路径 MUST 由 Profile 声明

模型目录与 manifest 路径 MUST 由 adapter profile 声明（静态 manifest 引擎）或声明动态 catalog 模式（动态引擎）。

#### Scenario: provider-aware static manifest preserves provider metadata

- **WHEN** `qwen` 通过 manifest 模式读取静态模型目录
- **THEN** 模型项 MAY 同时携带 `provider`、`provider_id` 与 `model`
- **AND** 这些字段 MUST 作为 provider-aware 客户端选择依据保留下来

### Requirement: UI shell session config MUST use the shared layering contract
UI shell 会话配置 MUST 复用共享 config layering 能力，而不是由 qwen 专属 security capability 单独定义。

#### Scenario: qwen ui shell merges default runtime and enforced layers
- **WHEN** 系统为 qwen 准备 UI shell session-local settings
- **THEN** 它 MUST 按 `default -> runtime overrides -> enforced` 的顺序组装配置
- **AND** 它 MUST 将结果写入 session-local `.qwen/settings.json`
- **AND** enforced 层 MUST 具有最高优先级

