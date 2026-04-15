## MODIFIED Requirements

### Requirement: interactive 终态门禁 MUST 先判显式输出分支再决定生命周期
The target lifecycle contract MUST distinguish final vs pending JSON branches before any fallback logic.

#### Scenario: pending branch enters waiting_user
- **WHEN** the current turn emits a valid pending JSON branch
- **AND** `__SKILL_DONE__ = false`
- **AND** `message` and `ui_hints` are valid
- **THEN** the run MUST enter `waiting_user`

#### Scenario: final branch enters completion path
- **WHEN** the current turn emits a valid final JSON branch
- **AND** `__SKILL_DONE__ = true`
- **AND** business fields satisfy the output schema
- **THEN** the run MUST enter the completion path

#### Scenario: legacy soft completion is rollout-only
- **WHEN** historical notes mention completion without explicit done marker
- **THEN** they MUST be described as legacy rollout context only
- **AND** they MUST NOT define the target lifecycle contract

## ADDED Requirements

### Requirement: repair exhaustion MUST fall back without deciding waiting or failure directly
Repair retries MUST belong to the same attempt and MUST only return control to the existing lifecycle fallback when exhausted.

#### Scenario: repair stays attempt-local
- **WHEN** a turn enters repair retries
- **THEN** retries MUST remain inside the same attempt
- **AND** they MUST NOT increment `attempt_number`

#### Scenario: repair exhaustion returns control
- **WHEN** repair retries are exhausted
- **THEN** repair MUST stop
- **AND** control MUST return to the existing lifecycle normalization path
- **AND** repair exhaustion itself MUST NOT directly decide `waiting_user` or `failed`
