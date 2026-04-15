## MODIFIED Requirements

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
