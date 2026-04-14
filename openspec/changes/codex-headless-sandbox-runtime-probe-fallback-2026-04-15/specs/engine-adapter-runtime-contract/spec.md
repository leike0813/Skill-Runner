## ADDED Requirements

### Requirement: Codex headless sandbox availability MUST be determined by runtime probe

Codex headless execution MUST determine sandbox availability from a real runtime probe and persist
that result in a Codex-side sidecar asset.

#### Scenario: `LANDLOCK_ENABLED=0` marks Codex sandbox unavailable

- **WHEN** runtime probes Codex sandbox availability
- **AND** environment variable `LANDLOCK_ENABLED=0`
- **THEN** the probe result MUST be `available=false`
- **AND** it MUST use warning code `CODEX_SANDBOX_DISABLED_BY_ENV`

#### Scenario: missing bubblewrap marks Codex sandbox unavailable

- **WHEN** runtime probes Codex sandbox availability
- **AND** neither `bwrap` nor `bubblewrap` can be resolved
- **THEN** the probe result MUST be `available=false`
- **AND** it MUST use warning code `CODEX_SANDBOX_DEPENDENCY_MISSING`
- **AND** the missing dependency list MUST include `bubblewrap`

#### Scenario: bubblewrap uid-map failure marks Codex sandbox runtime unavailable

- **WHEN** runtime probes Codex sandbox availability
- **AND** the bubblewrap smoke test fails with `uid_map`, `Operation not permitted`, `Permission denied`, or equivalent initialization failure wording
- **THEN** the probe result MUST be `available=false`
- **AND** it MUST use warning code `CODEX_SANDBOX_RUNTIME_UNAVAILABLE`
- **AND** the diagnostic message MUST preserve the first failing line for troubleshooting

#### Scenario: successful smoke test marks Codex sandbox available

- **WHEN** runtime probes Codex sandbox availability
- **AND** the bubblewrap smoke test succeeds
- **THEN** the probe result MUST be `available=true`
- **AND** it MUST be persisted to `agent_home/.codex/sandbox_probe.json`

### Requirement: Codex headless fallback MUST downgrade both command and generated config

Codex headless fallback MUST be effective: when sandbox runtime is unavailable, the runtime MUST
downgrade both CLI intent and generated profile settings.

#### Scenario: unavailable probe downgrades headless argv and config together

- **WHEN** Codex headless start or resume runs with sandbox probe `available=false`
- **THEN** command construction MUST downgrade `--full-auto` to `--yolo`
- **AND** generated Codex profile settings MUST set `sandbox_mode = "danger-full-access"`
- **AND** generated Codex profile settings MUST preserve `approval_policy = "never"`

#### Scenario: available probe keeps declared sandboxed defaults

- **WHEN** Codex headless start or resume runs with sandbox probe `available=true`
- **THEN** command construction MAY keep `--full-auto`
- **AND** generated Codex profile settings MUST keep the declared sandboxed mode rather than forcing `danger-full-access`

#### Scenario: missing or unreadable sidecar does not fail open

- **WHEN** headless Codex needs sandbox availability
- **AND** `agent_home/.codex/sandbox_probe.json` is missing or unreadable
- **THEN** runtime MUST synchronously execute a fresh Codex sandbox probe
- **AND** it MUST persist the new probe result before command/config decisions are finalized

### Requirement: Codex sandbox status collection MUST reuse probe truth

Codex sandbox management status MUST surface the same persisted runtime probe truth used by the
headless launch path.

#### Scenario: status collection returns runtime probe detail

- **WHEN** management code collects Codex sandbox status
- **THEN** it MUST return the persisted or freshly probed Codex sandbox result
- **AND** it MUST surface `available`, `status`, `warning_code`, `message`, `dependencies`, and `missing_dependencies`
- **AND** it MUST NOT regress to an environment-variable-only heuristic once the runtime probe model exists
