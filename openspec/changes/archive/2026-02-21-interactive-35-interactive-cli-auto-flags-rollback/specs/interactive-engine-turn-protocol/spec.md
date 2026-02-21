## MODIFIED Requirements

### Requirement: Adapter CLI 命令构造 MUST 与执行模式一致
系统 MUST 在构造引擎 CLI 命令时保持自动执行参数策略一致：`auto` 与 `interactive` 两种模式都保留自动执行参数。

#### Scenario: Gemini/iFlow auto 模式命令
- **WHEN** Gemini 或 iFlow 以 `auto` 模式执行
- **THEN** 命令包含 `--yolo`

#### Scenario: Gemini/iFlow interactive 模式命令
- **WHEN** Gemini 或 iFlow 以 `interactive` 模式执行
- **THEN** 命令包含 `--yolo`

#### Scenario: Codex auto 模式命令
- **WHEN** Codex 以 `auto` 模式执行
- **THEN** 命令包含自动执行参数（`--full-auto` 或 `--yolo`）

#### Scenario: Codex interactive 模式命令
- **WHEN** Codex 以 `interactive` 模式执行
- **THEN** 命令包含自动执行参数（`--full-auto` 或 `--yolo`）

#### Scenario: interactive resume 回合命令
- **WHEN** run 在 `interactive` 模式执行 reply/resume 回合
- **THEN** 命令仍包含自动执行参数（`--yolo` / `--full-auto`）
