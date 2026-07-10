## ADDED Requirements

### Requirement: CodeBuddy persistent config MUST be provider partitioned

The runtime MUST use a stable configuration directory per virtual provider and MUST use the same provider directory for model probes, start, and resume.

#### Scenario: Providers run concurrently
- **WHEN** domestic and global jobs execute
- **THEN** they use different persistent directories and cannot read each other's session state

### Requirement: CodeBuddy run configuration MUST be system owned

Each run MUST materialize CODEBUDDY.md, .codebuddy/settings.json, .codebuddy/mcp.json, and .codebuddy/skills, with settings that disable updates, hooks, untrusted frontmatter hooks, and automatic project MCP loading.

#### Scenario: A skill requests custom settings
- **WHEN** skill or runtime input attempts to override managed settings
- **THEN** the adapter ignores or rejects the override and writes the system-owned settings
