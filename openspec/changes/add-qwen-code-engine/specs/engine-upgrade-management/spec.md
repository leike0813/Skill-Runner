## ADDED Requirements

### Requirement: Qwen Code CLI MUST be managed installable

The engine management layer SHALL support managed installation of `@qwen-code/qwen-code`.

#### Scenario: Install Qwen Code

- **WHEN** the user requests to install Qwen engine
- **THEN** the system MUST run npm install for `@qwen-code/qwen-code`
- **AND** it MUST verify the `qwen` binary is available
- **AND** it MUST update the engine status cache

### Requirement: Qwen CLI binary detection MUST support cross-platform

Qwen CLI detection SHALL support multiple binary names for cross-platform compatibility.

#### Scenario: Detect Qwen CLI on different platforms

- **WHEN** the system detects the Qwen CLI
- **THEN** it MUST check for `qwen` on Unix-like systems
- **AND** it MUST check for `qwen.cmd` on Windows
- **AND** it MUST check for `qwen.exe` on Windows

## MODIFIED Requirements

### Requirement: Engine upgrade manager includes qwen

The engine upgrade manager SHALL include `qwen` in its managed packages and default ensure paths.

#### Scenario: Qwen package configuration

- **WHEN** the upgrade manager loads engine configurations
- **THEN** it MUST read `cli_management.package` from the Qwen adapter profile
- **AND** it MUST use `@qwen-code/qwen-code` as the npm package name
