## MODIFIED Requirements

### Requirement: Adapter CLI 命令构造 MUST 与执行模式一致
系统 MUST 在构造引擎 CLI 命令时保持自动执行参数策略一致；Codex headless 自动执行参数的选择 MUST 受真实 sandbox runtime probe 结果治理，而不是只受 `LANDLOCK_ENABLED` 粗判断治理。

#### Scenario: Codex auto 模式在 sandbox 可用时保留 `--full-auto`

- **WHEN** Codex 以 `auto` 模式执行 headless start 回合
- **AND** Codex sandbox runtime probe 结果为 `available=true`
- **THEN** 命令 MUST 包含 `--full-auto`
- **AND** 命令 MUST NOT 因运行时 probe 治理而降级为 `--yolo`

#### Scenario: Codex interactive 模式在 sandbox 可用时保留 `--full-auto`

- **WHEN** Codex 以 `interactive` 模式执行 headless start 回合
- **AND** Codex sandbox runtime probe 结果为 `available=true`
- **THEN** 命令 MUST 包含 `--full-auto`

#### Scenario: Codex headless start 在 sandbox 不可用时降级为 `--yolo`

- **WHEN** Codex 构造 headless start 命令
- **AND** Codex sandbox runtime probe 结果为 `available=false`
- **THEN** 命令 MUST 包含 `--yolo`
- **AND** 命令 MUST NOT 再包含 `--full-auto`

#### Scenario: Codex headless resume 在 sandbox 不可用时降级为 `--yolo`

- **WHEN** Codex 构造 headless resume 命令
- **AND** Codex sandbox runtime probe 结果为 `available=false`
- **THEN** resume 命令 MUST 包含 `--yolo`
- **AND** resume 命令 MUST NOT 再包含 `--full-auto`

#### Scenario: Codex headless start 与 resume 共享同一 sandbox probe 真值

- **WHEN** Codex 在同一 headless runtime 中分别构造 start 与 resume 命令
- **THEN** 这两个路径 MUST 消费同一份 Codex sandbox probe 结果
- **AND** MUST NOT 由 start/resume 各自实现独立的 sandbox 可用性判定分支
