# engine-runtime-config-layering Specification

## Purpose
定义运行时配置的统一分层优先级（bootstrap/engine_default/skill_default/runtime_override/enforced）和 adapter profile 驱动的路径解析。

## MODIFIED Requirements

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
