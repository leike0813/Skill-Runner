## ADDED Requirements

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
