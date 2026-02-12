## ADDED Requirements

### Requirement: Converter logic is prompt-first and SKILL.md-driven
The converter skill MUST define conversion orchestration in `SKILL.md`, including semantic analysis, task-type classification, convertibility decision, and conversion strategy execution.

#### Scenario: Semantic conversion flow executed from SKILL.md
- **WHEN** the converter skill is invoked
- **THEN** conversion decisions are produced through the staged prompt flow in `SKILL.md` instead of script-only transformation logic

### Requirement: Convertibility decision uses fixed three-state classification
The converter MUST classify source skills into exactly one of `not_convertible`, `convertible_with_constraints`, or `ready_for_auto`.

#### Scenario: Classification result is deterministic and explicit
- **WHEN** source skill analysis completes
- **THEN** the converter outputs one and only one classification state from the fixed set

### Requirement: Non-convertible output returns failure reason only
For `not_convertible`, the converter MUST stop conversion and return failure reason without generating a converted package.

#### Scenario: Stop on non-convertible
- **WHEN** classification is `not_convertible`
- **THEN** conversion terminates and response contains failure reason only

### Requirement: Constraint-mode confirmation policy follows execution mode
For `convertible_with_constraints`, interactive mode SHALL request user confirmation before applying constraints, while auto mode MUST proceed with agent-selected constraints.

#### Scenario: Interactive confirmation required
- **WHEN** classification is `convertible_with_constraints` and mode is interactive
- **THEN** converter requests user confirmation before file generation

#### Scenario: Auto mode proceeds without manual confirmation
- **WHEN** classification is `convertible_with_constraints` and mode is auto
- **THEN** converter applies selected constraints and continues conversion

### Requirement: Skill package keeps complete output contract
Successful conversion MUST produce a complete install-ready package including required contracts and references.

#### Scenario: Complete package artifacts are generated
- **WHEN** conversion succeeds
- **THEN** output contains converted package artifacts, bundled `references/file_protocol.md`, and patched/generated `SKILL.md` referencing `references/file_protocol.md`

### Requirement: Only final validator script is retained in skill package
The converter skill package MUST contain only final validation scripting logic for contract checks; conversion scripts that implement transformation logic MUST be removed.

#### Scenario: Script scope reduced to validation only
- **WHEN** reviewing converter skill package scripts
- **THEN** only final validation script and its embedded validator dependency are present

### Requirement: Embedded validator must be runtime-independent and parity-aligned
The final validation script MUST use an embedded validator implementation equivalent to project `SkillPackageValidator`, without importing server runtime internals.

#### Scenario: Runtime-independent validation
- **WHEN** validation runs in agent runtime context without project service imports
- **THEN** validator executes and enforces install-contract checks successfully

#### Scenario: Validator parity maintained
- **WHEN** the same invalid/valid package cases are validated by embedded validator and project validator
- **THEN** pass/fail outcomes and primary error categories are equivalent

