# engine-runtime-config-layering Specification

## Purpose
定义运行时配置的统一分层优先级（bootstrap/engine_default/skill_default/runtime_override/enforced）和 adapter profile 驱动的路径解析。
## Requirements
### Requirement: 运行时配置组装 MUST 采用统一分层优先级

系统 MUST 为 `codex/gemini/iflow/opencode/qwen/claude` 采用统一配置组装顺序：`engine_default -> skill defaults -> runtime overrides -> enforced`。

#### Scenario: claude official 1m model enables 1m context without changing model injection path
- **GIVEN** Claude 选择的官方模型名带有 `[1m]`
- **WHEN** 系统组装 headless run 的 session-local `.claude/settings.json`
- **THEN** 系统 MUST 继续通过 `env.ANTHROPIC_MODEL` 写入原始模型名
- **AND** MUST 将 `env.CLAUDE_CODE_DISABLE_1M_CONTEXT` 覆盖为 `"0"`

#### Scenario: claude custom provider 1m model uses root model and default sonnet pinning
- **GIVEN** Claude 选择的 custom provider 模型规格为 `provider/model[1m]`
- **WHEN** 系统组装 session-local `.claude/settings.json`
- **THEN** 系统 MUST 写入 provider 鉴权与 base URL 环境变量
- **AND** MUST 写入 `env.ANTHROPIC_DEFAULT_SONNET_MODEL=<去掉[1m]后的 provider model>`
- **AND** MUST 在配置根上写入 `model="sonnet[1m]"`
- **AND** MUST NOT 在最终配置中保留 `env.ANTHROPIC_MODEL`

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

UI shell 会话配置 MUST 复用共享 config layering 能力，而不是为单个引擎维持独立的运行时配置分流逻辑。

#### Scenario: claude ui shell reuses the same 1m runtime override contract
- **GIVEN** 用户以 Claude custom provider 模型 `provider/model[1m]` 启动 UI shell
- **WHEN** 系统生成 session-local `.claude/settings.json`
- **THEN** 它 MUST 复用与 headless run 相同的 Claude 1M runtime override 规则
- **AND** 最终配置 MUST 与 headless run 在 `model` / `ANTHROPIC_DEFAULT_SONNET_MODEL` / `CLAUDE_CODE_DISABLE_1M_CONTEXT` 语义上保持一致

