## MODIFIED Requirements

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

### Requirement: UI shell session config MUST use the shared layering contract

UI shell 会话配置 MUST 复用共享 config layering 能力，而不是为单个引擎维持独立的运行时配置分流逻辑。

#### Scenario: claude ui shell reuses the same 1m runtime override contract
- **GIVEN** 用户以 Claude custom provider 模型 `provider/model[1m]` 启动 UI shell
- **WHEN** 系统生成 session-local `.claude/settings.json`
- **THEN** 它 MUST 复用与 headless run 相同的 Claude 1M runtime override 规则
- **AND** 最终配置 MUST 与 headless run 在 `model` / `ANTHROPIC_DEFAULT_SONNET_MODEL` / `CLAUDE_CODE_DISABLE_1M_CONTEXT` 语义上保持一致
