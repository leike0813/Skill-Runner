## MODIFIED Requirements

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
