## ADDED Requirements

### Requirement: Qwen UI shell MUST enforce security restrictions

The Qwen engine UI shell SHALL load session-local configuration that enforces strict security restrictions for tools and permissions.

#### Scenario: Load UI shell enforced configuration

- **WHEN** UI shell session is prepared for Qwen engine
- **THEN** it MUST load `ui_shell_enforced.json` from config assets
- **AND** it MUST merge configuration layers: default → runtime → enforced
- **AND** it MUST write the merged config to `<session_dir>/.qwen/settings.json`

#### Scenario: Enforce permissions default mode to plan

- **WHEN** UI shell configuration is generated
- **THEN** `permissions.defaultMode` MUST be set to `"plan"` (read-only, no edits or commands)
- **AND** `permissions.deny` MUST include dangerous tools: `Bash`, `Edit`, `Write`, `Glob`, `Grep`, `Read`, `Agent`, `Skill`
- **AND** `permissions.allow` MUST be empty (no auto-approved dangerous operations)

#### Scenario: Set approval mode to plan

- **WHEN** UI shell configuration is generated
- **THEN** `tools.approvalMode` MUST be set to `"plan"`
- **AND** this restricts Qwen to read-only analysis without file edits or shell commands

### Requirement: Qwen config schema MUST validate permissions and tools

The Qwen configuration schema SHALL include definitions for `permissions` and `tools` fields following Qwen Code's actual configuration format.

#### Scenario: Validate permissions object

- **WHEN** configuration JSON is validated against schema
- **THEN** `permissions` object MUST accept `defaultMode`, `allow`, `ask`, `deny` fields
- **AND** `defaultMode` MUST be one of: `["plan", "default", "auto-edit", "yolo"]`

#### Scenario: Validate tools object

- **WHEN** configuration JSON is validated against schema
- **THEN** `tools` object MUST accept `sandbox` and `approvalMode` fields
- **AND** `approvalMode` MUST be one of: `["plan", "default", "auto-edit", "yolo"]`
- **AND** `sandbox` MAY be a boolean or string (for custom sandbox paths)

### Requirement: Qwen adapter profile MUST declare UI shell config assets

The Qwen adapter profile SHALL specify the paths to UI shell configuration files in the `ui_shell.config_assets` section.

#### Scenario: Resolve UI shell default config path

- **WHEN** the runtime calls `profile.resolve_ui_shell_default_config_path()`
- **THEN** it MUST return the path to `ui_shell_default.json`
- **AND** this file MUST exist in `server/engines/qwen/config/`

#### Scenario: Resolve UI shell enforced config path

- **WHEN** the runtime calls `profile.resolve_ui_shell_enforced_config_path()`
- **THEN** it MUST return the path to `ui_shell_enforced.json`
- **AND** this file MUST exist in `server/engines/qwen/config/`

#### Scenario: Resolve UI shell settings schema path

- **WHEN** the runtime calls `profile.resolve_ui_shell_settings_schema_path()`
- **THEN** it MUST return the path to `qwen_config_schema.json`
- **AND** this schema MUST validate the merged configuration

#### Scenario: Resolve UI shell target relpath

- **WHEN** the runtime calls `profile.resolve_ui_shell_target_relpath()`
- **THEN** it MUST return `.qwen/settings.json`
- **AND** this is the path where Qwen Code expects its settings file

## Security Considerations

### Threat Model

The UI shell is designed for interactive testing and authentication. The security restrictions prevent:

1. **File system writes** - `permissions.deny` includes `Edit` and `Write`
2. **Shell command execution** - `permissions.deny` includes `Bash`
3. **Unrestricted file reads** - `permissions.deny` includes `Read`, `Glob`, `Grep`
4. **Agent/sub-agent creation** - `permissions.deny` includes `Agent` and `Skill`

### Limitations

1. **No sandbox enforcement** - Qwen Code sandbox (`tools.sandbox`) requires Docker/Podman or macOS Seatbelt, which may not be available in all environments
2. **Permission bypass possible** - Without sandbox, permissions are enforced at the application level only, not at the OS level
3. **Network access not fully blocked** - `WebFetch` is not explicitly denied but requires the tool to be available

### Mitigation

1. **UI shell is for testing only** - Not intended for production or untrusted code execution
2. **Plan mode default** - Read-only mode prevents modifications by default
3. **Explicit deny list** - Dangerous tools are explicitly denied via `permissions.deny`
4. **Approval mode** - `tools.approvalMode: "plan"` provides defense in depth
