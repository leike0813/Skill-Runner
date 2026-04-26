## ADDED Requirements

### Requirement: Claude adapter MUST use active state for MCP lifecycle
The Claude adapter SHALL prepare and clean up governed MCP state using the active Claude state file derived from the runtime `CLAUDE_CONFIG_DIR`.

#### Scenario: Claude run starts with run-local MCP
- **WHEN** a Claude run resolves run-local MCP servers
- **THEN** the adapter MUST materialize those servers into the current run project entry before launching Claude

#### Scenario: Claude run reaches terminal cleanup
- **WHEN** a Claude run used run-local MCP entries
- **THEN** the adapter MUST attempt to remove those run-local entries during terminal cleanup
- **AND** cleanup failure MUST NOT change the terminal run outcome

