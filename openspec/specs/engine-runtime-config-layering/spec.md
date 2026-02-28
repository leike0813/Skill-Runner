# engine-runtime-config-layering Specification

## Purpose
TBD - created by archiving change engine-config-layering-and-opencode-permission-modes. Update Purpose after archive.
## Requirements
### Requirement: 运行时配置组装 MUST 采用统一分层优先级
系统 MUST 为 `codex/gemini/iflow/opencode` 采用统一配置组装顺序：`engine_default -> skill defaults -> runtime overrides -> enforced`。

#### Scenario: 各层均存在同名键冲突
- **WHEN** 同一配置键在多个层中同时出现
- **THEN** 后一层 MUST 覆盖前一层
- **AND** 最终结果满足 `enforced` 最高优先级

#### Scenario: skill/runtime 未提供模型
- **WHEN** skill defaults 与 runtime overrides 均未设置模型字段
- **THEN** 系统 MUST 使用 `engine_default` 的模型配置作为运行时输入
- **AND** MUST NOT 依赖 CLI 历史状态作为主要兜底路径

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

#### Scenario: 静态 manifest 引擎模型读取
- **WHEN** `codex/gemini/iflow` 加载模型清单
- **THEN** 使用 profile 中的 `model_catalog.manifest_path`（或等价 root+manifest）定位模型目录

#### Scenario: 动态 catalog 引擎模型读取
- **WHEN** `opencode` 执行动态模型探测/缓存加载
- **THEN** seed/cache 路径与模式来自 profile 中的 `model_catalog` 元信息
- **AND** 动态探测行为语义保持不变
