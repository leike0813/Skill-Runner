## ADDED Requirements

### Requirement: Local bootstrap MUST prepare CodeBuddy managed storage

Local deployment bootstrap MUST make CodeBuddy credential and provider config roots available with owner-only permissions where secrets or session state can be stored. It MUST NOT create a CodeBuddy runtime model-cache root.

#### Scenario: A fresh local deployment starts
- **WHEN** CodeBuddy has not previously been used
- **THEN** first use yields deterministic data-dir and agent-home paths without reading host CodeBuddy state

### Requirement: Managed bootstrap defaults MUST install only OpenCode and Codex

When no explicit engine selection is supplied, local installers, control commands, development containers, and release containers MUST resolve the managed bootstrap set to `opencode,codex`. Claude, Qwen, Kilo, and CodeBuddy MUST remain supported on-demand targets. Gemini MUST remain deprecated and MUST NOT be accepted by explicit subsets or included by `all`.

#### Scenario: Bootstrap runs without an override
- **WHEN** neither `--engines` nor `SKILL_RUNNER_BOOTSTRAP_ENGINES` supplies a value
- **THEN** only OpenCode and Codex are requested and every other supported engine is reported as skipped

#### Scenario: Deprecated Gemini is explicitly requested
- **WHEN** `--engines gemini` or the equivalent environment override is supplied
- **THEN** bootstrap rejects Gemini as unsupported without starting an install
