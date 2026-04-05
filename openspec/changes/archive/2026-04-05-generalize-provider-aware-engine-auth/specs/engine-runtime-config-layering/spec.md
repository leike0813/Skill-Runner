## MODIFIED Requirements

### Requirement: 运行时配置组装 MUST 采用统一分层优先级

系统 MUST 为 `codex/gemini/iflow/opencode/qwen` 采用统一配置组装顺序：`engine_default -> skill defaults -> runtime overrides -> enforced`。

#### Scenario: qwen joins the shared layering contract

- **WHEN** `qwen` 执行运行时配置组装
- **THEN** 系统 MUST 先应用 `engine_default`
- **AND** 再按统一优先级合并 skill defaults、runtime overrides 与 enforced

### Requirement: 模型目录与 Manifest 路径 MUST 由 Profile 声明

模型目录与 manifest 路径 MUST 由 adapter profile 声明（静态 manifest 引擎）或声明动态 catalog 模式（动态引擎）。

#### Scenario: provider-aware static manifest preserves provider metadata

- **WHEN** `qwen` 通过 manifest 模式读取静态模型目录
- **THEN** 模型项 MAY 同时携带 `provider`、`provider_id` 与 `model`
- **AND** 这些字段 MUST 作为 provider-aware 客户端选择依据保留下来
