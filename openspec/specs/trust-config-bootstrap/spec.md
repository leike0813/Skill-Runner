# trust-config-bootstrap Specification

## Purpose
定义容器启动时 trust 配置文件的 bootstrap 和 trusted parent run 目录初始化策略。
## Requirements
### Requirement: Bootstrap trust config files at container startup
At container startup, the system MUST ensure trust configuration artifacts required by Codex and Gemini exist and are valid.

#### Scenario: Create missing Gemini trusted folders file
- **WHEN** `~/.gemini/trustedFolders.json` does not exist
- **THEN** the system creates the file with a top-level JSON object (`{}`)

#### Scenario: Repair invalid Gemini trusted folders file
- **WHEN** `~/.gemini/trustedFolders.json` exists but is not a valid JSON object
- **THEN** the system repairs it to a valid JSON object and preserves a backup of the previous content

### Requirement: Bootstrap trusted parent run directory
At startup, the system MUST pre-register the run parent directory as trusted for Codex and Gemini.

#### Scenario: Bootstrap Codex parent trust
- **WHEN** startup initializes runtime environment
- **THEN** Codex config contains `projects."<runs_parent>".trust_level = "trusted"`

#### Scenario: Bootstrap Gemini parent trust
- **WHEN** startup initializes runtime environment
- **THEN** Gemini trusted folders map contains `"<runs_parent>": "TRUST_FOLDER"`

### Requirement: Bootstrap is idempotent
Repeated startup runs MUST preserve valid configuration and avoid duplicate or conflicting trust entries.

#### Scenario: Startup rerun with existing trust entries
- **WHEN** startup logic executes multiple times
- **THEN** trust entries for run parent remain correct without duplicated/invalid structure

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

