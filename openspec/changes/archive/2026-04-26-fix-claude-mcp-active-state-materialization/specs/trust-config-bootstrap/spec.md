## ADDED Requirements

### Requirement: Claude bootstrap and trust MUST target active state
Claude bootstrap and trust-folder state SHALL use the same active state file that Claude Code reads under Skill-Runner's runtime environment.

#### Scenario: Claude layout is initialized
- **WHEN** Skill-Runner initializes managed agent layout for Claude
- **THEN** it MUST create or repair `agent_home/.claude/.claude.json`
- **AND** it MUST NOT rely on `agent_home/.claude.json` as the new write target

#### Scenario: Legacy Claude state exists
- **WHEN** `agent_home/.claude.json` exists and the active state file is absent
- **THEN** the system MUST migrate compatible object content into the active state file

### Requirement: Claude trust operations MUST use active state projects
Claude run-folder trust operations SHALL read and write project entries in the active state file.

#### Scenario: Run folder is trusted
- **WHEN** a Claude run folder is registered as trusted
- **THEN** the active state file MUST contain `projects[str(run_dir.resolve())].hasTrustDialogAccepted=true`

