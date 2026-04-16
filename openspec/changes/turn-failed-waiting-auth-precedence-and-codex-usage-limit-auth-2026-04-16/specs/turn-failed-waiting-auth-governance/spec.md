# turn-failed-waiting-auth-governance Specification

## ADDED Requirements

### Requirement: waiting-auth MUST take canonical precedence over semantic turn failure

The system MUST treat `agent.turn_failed` as engine evidence only when high-confidence auth remediation successfully creates pending auth.

#### Scenario: semantic turn failure coexists with pending auth

- **WHEN** runtime evidence contains semantic `turn.failed`
- **AND** high-confidence auth detection successfully creates `pending_auth` or `pending_auth_method_selection`
- **THEN** the canonical run status MUST be `waiting_auth`
- **AND** the system MUST NOT project a terminal failed state from that same attempt

### Requirement: waiting-auth MUST preserve a user-visible reason message

The system MUST preserve the semantic failure reason that led to authentication remediation and surface it through the waiting-auth payload.

#### Scenario: waiting-auth is entered after semantic engine failure

- **WHEN** the run enters `waiting_auth`
- **AND** semantic `turn_failed.message` or equivalent auth-related runtime diagnostics are available
- **THEN** the waiting-auth payload MUST carry that reason in `last_error`
- **AND** the waiting-auth instructions MUST preserve the message for user display

### Requirement: Codex usage-limit patterns MUST enter waiting-auth as high-confidence auth blockers

The system MUST classify Codex usage-limit / entitlement failures as high-confidence auth-remediable blockers.

#### Scenario: Codex hits a usage-limit failure

- **WHEN** Codex emits a usage-limit style message such as `You've hit your usage limit. Upgrade to Plus ...`
- **THEN** Codex auth detection MUST classify the run as high-confidence `auth_required`
- **AND** orchestration MUST be able to enter `waiting_auth`
- **AND** semantic `agent.turn_failed` MUST still be preserved when a `turn.failed` row exists
