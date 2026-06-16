## MODIFIED Requirements

### Requirement: Runtime SKILL patch MUST use a fixed composition order
系统 MUST 按固定顺序组合 runtime `SKILL.md` 注入模块，避免静态模板与动态合同重复表达同一语义。When `runtime_options.collect_skill_run_feedback=true`, the optional feedback module MUST be appended as the final section of the run-local `SKILL.md`.

#### Scenario: runtime skill patch composition
- **WHEN** 运行时为 skill 生成 patch plan
- **THEN** 注入顺序 MUST 为 Runtime Enforcement → Runtime Output Overrides → Output Format Contract → Output Contract Details → Execution Mode
- **AND** Execution Mode 模块 MUST 出现在动态 contract details 之后

#### Scenario: feedback patch is last when enabled
- **WHEN** `collect_skill_run_feedback` is true for the current run
- **THEN** the runtime-patched run-local `SKILL.md` MUST end with the Skill Run Feedback section
- **AND** the source skill package MUST NOT be modified
- **AND** run-root instruction files MUST NOT receive this feedback patch

### Requirement: Skill run feedback patch MUST render the protocol template with an explicit path

The feedback patch section SHALL be injected only when `runtime_options.collect_skill_run_feedback=true` and SHALL render the Skill Run Feedback Sidecar protocol template with the current run's explicit feedback sidecar path.

#### Scenario: feedback patch rendered path
- **WHEN** feedback collection is enabled
- **THEN** the injected section content MUST include the explicit `result/<namespace>/_skill_run_feedback.md` path for the current run
- **AND** the injected section content MUST preserve the Skill Run Feedback Sidecar protocol wording around that path

#### Scenario: feedback patch disabled
- **WHEN** feedback collection is omitted or false
- **THEN** the feedback section MUST NOT be injected
