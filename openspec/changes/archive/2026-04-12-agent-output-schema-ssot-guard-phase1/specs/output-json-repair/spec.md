## MODIFIED Requirements

### Requirement: 系统 MUST 在输出解析阶段执行 deterministic generic repair
The system MUST evolve output repair into a bounded schema-convergence loop that works for both `auto` and `interactive` modes while remaining same-attempt and deterministic.

#### Scenario: repair loop is attempt-local
- **WHEN** a turn enters schema repair
- **THEN** all repair retries MUST execute within the current attempt
- **AND** repair MUST NOT increment `attempt_number`

#### Scenario: repair retry budget is bounded
- **WHEN** a turn enters schema repair
- **THEN** the system MUST enforce a bounded retry budget
- **AND** the default retry budget MUST be 3

### Requirement: 系统 MUST 维持 Schema-first 成功标准
The target success rule MUST remain schema-first, but repair exhaustion MUST fall back to existing lifecycle logic rather than directly deciding waiting or terminal state on its own.

#### Scenario: repaired final object succeeds
- **WHEN** repair produces a compliant final JSON object
- **AND** business fields pass output schema validation
- **THEN** the turn MAY continue on the completion path

#### Scenario: repaired pending object waits
- **WHEN** repair produces a compliant pending JSON object
- **AND** the payload has `__SKILL_DONE__ = false`
- **AND** the payload includes valid `message` and `ui_hints`
- **THEN** the turn MAY continue on the waiting-user path

#### Scenario: repair exhaustion returns to lifecycle fallback
- **WHEN** repair exhausts its retry budget without producing a compliant branch
- **THEN** repair MUST stop
- **AND** the system MUST return control to the existing lifecycle normalization path
- **AND** repair exhaustion itself MUST NOT directly classify the turn as `waiting_user`

## ADDED Requirements

### Requirement: Repair audit MUST preserve convergence evidence
Future compliant implementations MUST record the repair process as explicit audit evidence.

#### Scenario: repair audit captures retry context
- **WHEN** schema repair executes
- **THEN** audit expectations MUST include raw output, extracted JSON candidate, validation errors, repair round index, and convergence or fallback outcome
