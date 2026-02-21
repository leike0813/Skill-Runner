## MODIFIED Requirements

### Requirement: Adapter CLI 命令构造 MUST 与执行模式一致
系统 MUST 在构造引擎 CLI 命令时保持自动执行参数策略一致：`auto` 与 `interactive` 两种模式都保留自动执行参数。  
并且 iFlow 在所有执行场景 MUST 默认包含 `--thinking` 参数。

#### Scenario: Gemini auto 模式命令
- **WHEN** Gemini 以 `auto` 模式执行
- **THEN** 命令包含 `--yolo`

#### Scenario: Gemini interactive 模式命令
- **WHEN** Gemini 以 `interactive` 模式执行
- **THEN** 命令包含 `--yolo`

#### Scenario: iFlow auto 模式命令
- **WHEN** iFlow 以 `auto` 模式执行
- **THEN** 命令包含 `--yolo`
- **AND** 命令包含 `--thinking`

#### Scenario: iFlow interactive 模式命令
- **WHEN** iFlow 以 `interactive` 模式执行
- **THEN** 命令包含 `--yolo`
- **AND** 命令包含 `--thinking`

#### Scenario: Codex auto 模式命令
- **WHEN** Codex 以 `auto` 模式执行
- **THEN** 命令包含自动执行参数（`--full-auto` 或 `--yolo`）

#### Scenario: Codex interactive 模式命令
- **WHEN** Codex 以 `interactive` 模式执行
- **THEN** 命令包含自动执行参数（`--full-auto` 或 `--yolo`）

#### Scenario: interactive resume 回合命令
- **WHEN** run 在 `interactive` 模式执行 reply/resume 回合
- **THEN** Gemini 命令包含自动执行参数（`--yolo`）
- **AND** iFlow 命令包含自动执行参数（`--yolo`）与 `--thinking`
- **AND** Codex 命令包含自动执行参数（`--yolo` / `--full-auto`）
