# output-json-repair Specification

## Purpose
定义输出解析阶段的 deterministic generic repair 策略和 Schema-first 成功标准。
## Requirements
### Requirement: 系统 MUST 在输出解析阶段执行 deterministic generic repair
The target repair model MUST be described as a bounded schema-convergence loop for both `auto` and `interactive`.

#### Scenario: repair retry budget is attempt-local
- **WHEN** a turn enters repair
- **THEN** repair retries MUST stay inside the current attempt
- **AND** they MUST NOT increase `attempt_number`

#### Scenario: repair is bounded
- **WHEN** repair executes
- **THEN** it MUST use a bounded retry budget
- **AND** the default retry budget MUST be 3

### Requirement: 系统 MUST 维持 Schema-first 成功标准
The target success rule MUST remain schema-first, and repair exhaustion MUST only return control to lifecycle fallback.

#### Scenario: compliant repaired final object may complete
- **WHEN** repair yields a compliant final JSON object
- **THEN** the turn MAY continue on the completion path

#### Scenario: compliant repaired pending object may wait
- **WHEN** repair yields a compliant pending JSON object
- **THEN** the turn MAY continue on the waiting-user path

#### Scenario: repair exhaustion is not a terminal classifier
- **WHEN** repair exhausts its retry budget without a compliant branch
- **THEN** repair MUST stop
- **AND** the system MUST return control to the existing lifecycle normalization path
- **AND** repair exhaustion itself MUST NOT directly classify the turn as `waiting_user` or `failed`

### Requirement: Repair-success 结果 MUST 可缓存
对于 repair 后成功且 schema 通过的结果，系统 MUST 允许写入 cache。

#### Scenario: Repair-success 缓存
- **WHEN** run 通过 deterministic repair 达到 success
- **THEN** 系统记录 cache entry
- **AND** 后续相同请求可命中该结果

### Requirement: 系统 MUST 在主路径失败后尝试结果文件兜底恢复

当 deterministic generic repair 与主路径结构化输出提取无法得到合法最终结果时，系统 MUST 可在 run 工作目录内尝试恢复结果文件。

#### Scenario: stdout 缺失时由结果文件恢复成功
- **GIVEN** run `exit_code == 0`
- **AND** stdout/stream 未能提供可解析的最终 JSON
- **AND** `run_dir` 中存在合法的 `<skill-id>.result.json`
- **WHEN** lifecycle 执行终态标准化
- **THEN** 系统必须使用该文件内容作为最终 `output_data`
- **AND** run 状态为成功
- **AND** 结果包含 warning `OUTPUT_RECOVERED_FROM_RESULT_FILE`

#### Scenario: stdout JSON schema 非法时由结果文件恢复成功
- **GIVEN** run `exit_code == 0`
- **AND** stdout/stream 中提取出的 JSON 未通过 `output.schema`
- **AND** `run_dir` 中存在通过 schema 的结果文件
- **WHEN** lifecycle 执行终态标准化
- **THEN** 系统必须改用结果文件内容作为最终 `output_data`
- **AND** run 状态为成功

#### Scenario: 结果文件非法时保持失败
- **GIVEN** run `exit_code == 0`
- **AND** 主路径未得到合法最终 JSON
- **AND** 命中的结果文件 JSON 非法或不满足 `output.schema`
- **WHEN** lifecycle 执行终态标准化
- **THEN** run 状态必须保持失败
- **AND** 结果必须包含对应 warning

### Requirement: Repair prompts MUST reuse the runtime output contract builder
系统 MUST 让 repair prompt 复用与 runtime `SKILL.md` 注入相同的动态 output contract builder，避免维护第二套 prompt summary wording。

#### Scenario: build repair prompt contract
- **WHEN** orchestrator 为某个 attempt 构建 schema repair prompt
- **THEN** repair prompt 中的 contract details MUST 来自统一动态 builder
- **AND** 该文本 MUST 与当前引擎有效的 prompt contract 保持一致

#### Scenario: prompt contract artifact removed
- **WHEN** run 目录中不存在 prompt-facing schema Markdown artifact
- **THEN** repair prompt 构建 MUST 仍然成功
- **AND** 系统 MUST NOT 依赖 `.audit/contracts/*.md` summary 文件

### Requirement: Repair audit MUST preserve convergence evidence
Future compliant implementations MUST record the repair process as explicit audit evidence.

#### Scenario: repair audit captures retry context
- **WHEN** schema repair executes
- **THEN** audit expectations MUST include raw output, extracted JSON candidate, validation errors, repair round index, and convergence or fallback outcome

### Requirement: Attempt-Level Output Convergence Loop

Each runtime attempt MUST be governed by one orchestrator-owned output convergence loop.

#### Scenario: Deterministic parse repair runs inside each loop iteration
- **WHEN** an attempt produces raw assistant output
- **THEN** the orchestrator MUST first apply deterministic parse normalization for that loop iteration
- **AND** only the normalized candidate is validated against the attempt target schema
- **AND** downstream fallback logic MUST NOT repeat deterministic parse repair after loop exhaustion

#### Scenario: Repair reruns are handle-gated
- **WHEN** the attempt output still does not satisfy the target schema after deterministic parse normalization
- **THEN** the orchestrator MAY issue a repair rerun only if a persisted session handle already exists
- **AND** the rerun MUST stay within the same `attempt_number`
- **AND** the rerun MUST increment `internal_round_index`

#### Scenario: No session handle skips repair
- **WHEN** a repair rerun would otherwise be required but no session handle exists
- **THEN** the orchestrator MUST emit `diagnostic.output_repair.skipped`
- **AND** the skip reason MUST identify the missing session handle
- **AND** runtime MUST continue via the legacy fallback chain without a repair rerun

### Requirement: 系统 MUST 通过统一 output convergence executor 管理修复链
The target repair model MUST be governed by a single orchestrator-side output convergence executor.

#### Scenario: deterministic parse repair is pre-processing, not a separate owner
- **WHEN** parser or adapter yields a repaired JSON candidate
- **THEN** that repaired candidate MUST re-enter the orchestrator-owned output convergence pipeline
- **AND** parser/adapter repair MUST NOT become a separate completion or waiting classifier

#### Scenario: result-file fallback remains inside the same governance model
- **WHEN** the primary structured-output path fails to converge
- **THEN** result-file fallback MUST be described as a legacy downstream stage within the same output convergence model
- **AND** it MUST NOT be described as an unrelated recovery subsystem

### Requirement: 系统 MUST 使用 `attempt + internal_round` 双层 repair 模型
The target repair model MUST distinguish outer attempts from inner convergence rounds.

#### Scenario: repair rounds stay inside the current attempt
- **WHEN** a turn enters repair
- **THEN** each convergence retry MUST be represented as an `internal_round`
- **AND** the retries MUST stay inside the current `attempt_number`

#### Scenario: repair round budget is bounded
- **WHEN** repair executes
- **THEN** the default `internal_round` retry budget MUST be 3
- **AND** exhaustion MUST return control to legacy lifecycle fallback instead of creating a new attempt

### Requirement: Repair MUST remain schema-first while preserving legacy fallback ordering
Repair MUST only converge when a compliant branch exists; otherwise the target model MUST return control to the legacy fallback chain in a fixed order.

#### Scenario: compliant final branch converges
- **WHEN** output convergence yields a compliant final JSON object
- **THEN** the turn MAY continue on the completion path

#### Scenario: repair exhaustion returns to legacy chain
- **WHEN** the `internal_round` budget is exhausted without a compliant branch
- **THEN** the output convergence executor MUST stop repair
- **AND** it MUST return control to legacy lifecycle fallback first
- **AND** later legacy stages MAY still include result-file fallback or interactive waiting heuristics

