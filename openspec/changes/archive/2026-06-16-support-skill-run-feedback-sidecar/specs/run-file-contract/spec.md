## ADDED Requirements

### Requirement: Skill run feedback sidecar MUST be optional and result-local

The system SHALL treat `_skill_run_feedback.md` as an optional Markdown sidecar located in the same directory as the actual terminal `result.json`.

#### Scenario: successful run may produce feedback
- **WHEN** a run succeeds and its actual result path is `result/<namespace>/result.json`
- **THEN** the agent may write `result/<namespace>/_skill_run_feedback.md`
- **AND** the file MUST NOT be required by output schema
- **AND** the file MUST NOT be added to `result.json`

#### Scenario: non-success routes do not require feedback
- **WHEN** a run fails, is canceled, is pending, or is waiting for user input
- **THEN** the feedback sidecar MUST NOT be required
- **AND** absence of the sidecar MUST NOT affect that route

#### Scenario: feedback sidecar diagnostics do not change terminal status
- **WHEN** a successful run has missing, empty, or unreadable feedback sidecar state
- **THEN** the system records diagnostic logs only
- **AND** the run remains succeeded

### Requirement: Normal bundles MUST include present feedback sidecars

Normal run bundles SHALL include `_skill_run_feedback.md` when the file exists beside an included terminal `result.json`.

#### Scenario: namespaced feedback sidecar is bundled
- **WHEN** a bundle is built and `result/<namespace>/_skill_run_feedback.md` exists beside `result/<namespace>/result.json`
- **THEN** the bundle includes `result/<namespace>/_skill_run_feedback.md`
- **AND** existing business artifacts and result layout are unchanged

#### Scenario: legacy feedback sidecar is bundled
- **WHEN** a legacy run has `result/_skill_run_feedback.md` beside `result/result.json`
- **THEN** the bundle includes `result/_skill_run_feedback.md`
