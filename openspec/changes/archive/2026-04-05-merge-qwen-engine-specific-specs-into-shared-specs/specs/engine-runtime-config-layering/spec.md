## ADDED Requirements

### Requirement: UI shell session config MUST use the shared layering contract
UI shell 会话配置 MUST 复用共享 config layering 能力，而不是由 qwen 专属 security capability 单独定义。

#### Scenario: qwen ui shell merges default runtime and enforced layers
- **WHEN** 系统为 qwen 准备 UI shell session-local settings
- **THEN** 它 MUST 按 `default -> runtime overrides -> enforced` 的顺序组装配置
- **AND** 它 MUST 将结果写入 session-local `.qwen/settings.json`
- **AND** enforced 层 MUST 具有最高优先级
