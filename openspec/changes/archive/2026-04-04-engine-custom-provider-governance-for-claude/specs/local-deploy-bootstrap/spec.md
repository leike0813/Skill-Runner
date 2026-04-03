## MODIFIED Requirements

### Requirement: Claude bootstrap initializes .claude.json onboarding state

Local bootstrap for Claude SHALL initialize the global Claude state file rather than runtime project settings.

#### Scenario: ensure Claude layout

- **WHEN** bootstrap ensures Claude agent-home layout
- **THEN** it MUST write bootstrap payload into `agent_home/.claude.json`
- **AND** that payload MUST set `hasCompletedOnboarding=true`
- **AND** it MUST NOT treat `bootstrap.json` as the source of `run_dir/.claude/settings.json`
