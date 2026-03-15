## ADDED Requirements

### Requirement: request_input audit MUST capture first-attempt rendered prompt and effective spawn command
系统 MUST 在 `.audit/request_input.json` 记录首 attempt 的最终渲染 prompt 与实际执行命令信息，用于跨平台排障。

#### Scenario: attempt 1 writes rendered prompt and effective argv
- **GIVEN** run 正在执行首个 attempt
- **WHEN** runtime 完成 prompt 渲染与最终执行命令确定
- **THEN** `.audit/request_input.json` MUST 包含 `rendered_prompt_first_attempt`
- **AND** MUST 包含 `spawn_command_original_first_attempt`
- **AND** MUST 包含 `spawn_command_effective_first_attempt`
- **AND** MUST 包含 `spawn_command_normalization_applied_first_attempt`
- **AND** MUST 包含 `spawn_command_normalization_reason_first_attempt`

#### Scenario: attempt greater than 1 does not overwrite first-attempt fields
- **GIVEN** run 进入第二次及后续 attempt
- **WHEN** runtime 继续执行
- **THEN** 系统 MUST NOT 新写或覆盖 `*_first_attempt` 字段

### Requirement: audit write failures MUST degrade to fallback files without blocking run
当 `.audit/request_input.json` 无法写入时，系统 MUST 降级写入回退审计文件，且不得中断 run 主流程。

#### Scenario: request_input json unavailable
- **GIVEN** `.audit/request_input.json` 缺失、损坏或写入失败
- **WHEN** runtime 执行首 attempt 审计写入
- **THEN** 系统 MUST 以 best-effort 写入 `.audit/prompt.1.txt` 与 `.audit/argv.1.json`
- **AND** run 主流程 MUST continue
