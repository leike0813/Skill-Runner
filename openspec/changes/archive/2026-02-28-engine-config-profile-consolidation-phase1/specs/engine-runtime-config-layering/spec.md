## MODIFIED Requirements

### Requirement: Runtime Config Layering MUST Resolve Engine Asset Paths from Adapter Profile
系统在执行 `engine_default -> skill defaults -> runtime overrides -> enforced` 分层组装时，MUST 从 adapter profile 解析各层资产路径。

#### Scenario: Layer files resolved via profile
- **WHEN** 任一引擎执行配置分层组装
- **THEN** `default/enforced/skill-defaults` 文件路径来自该引擎 `adapter_profile.json`
- **AND** 不依赖 `core_config` 中引擎专属路径键

### Requirement: Bootstrap Path Ownership MUST Move to Adapter Profile
bootstrap 配置文件路径 MUST 由 adapter profile 声明，用于统一引擎资产归档与可审计性。

#### Scenario: Bootstrap path lookup
- **WHEN** agent layout/bootstrap 逻辑读取引擎 bootstrap 文件
- **THEN** 路径来自 adapter profile 的 `config_assets.bootstrap_path`
- **AND** 引擎迁移或重命名无需修改公共配置中心

### Requirement: Model Manifest/Root Paths MUST Be Profile-Declared
模型目录与 manifest 路径 MUST 由 adapter profile 声明（静态 manifest 引擎）或声明动态 catalog 模式（动态引擎）。

#### Scenario: Static manifest engine model lookup
- **GIVEN** `codex/gemini/iflow` 模型读取
- **WHEN** `ModelRegistry` 加载模型 catalog
- **THEN** 使用 profile 中的 `model_catalog.manifest_path`（或等价 root+manifest）定位模型清单

#### Scenario: Dynamic catalog engine model lookup
- **GIVEN** `opencode` 动态模型探测
- **WHEN** 读取 seed/cache 配置
- **THEN** 路径与模式来自 profile 中的 `model_catalog` 元信息
- **AND** 动态探测行为语义保持不变
