## ADDED Requirements

### Requirement: UI engine list MUST include qwen

The engine management UI SHALL display `qwen` as an available engine.

#### Scenario: Display Qwen in engine list

- **WHEN** the user opens the engine management page
- **THEN** the UI MUST show `Qwen Code` with identifier `qwen`
- **AND** it MUST display installation status
- **AND** it MUST display version if installed

### Requirement: UI MUST allow installing Qwen engine

The engine management UI SHALL provide an install action for Qwen.

#### Scenario: Install Qwen from UI

- **WHEN** the user clicks "Install" on the Qwen engine card
- **THEN** the UI MUST trigger the install/upgrade API
- **AND** it MUST show progress
- **AND** it MUST update the rendered status after completion

### Requirement: UI MUST expose qwen provider-aware auth options

The Qwen entry in `/ui/engines` SHALL expose provider-aware auth actions that match the backend strategy matrix.

#### Scenario: Qwen auth menu shows three providers

- **WHEN** the user opens the Qwen auth menu
- **THEN** the UI MUST show:
  - `Qwen OAuth (Free)`
  - `Coding Plan (China)`
  - `Coding Plan (Global)`

#### Scenario: Qwen OAuth shows import action

- **WHEN** the selected provider is `qwen-oauth`
- **THEN** the UI MUST show the import credentials entry

#### Scenario: Qwen Coding Plan hides import action

- **WHEN** the selected provider is `coding-plan-china` or `coding-plan-global`
- **THEN** the UI MUST NOT show the import credentials entry

## MODIFIED Requirements

### Requirement: Engine selector includes qwen

The run form engine selector SHALL include `qwen` as an option.

#### Scenario: Select Qwen engine for a run

- **WHEN** the user creates a new run
- **THEN** the engine selector MUST include `Qwen Code`
- **AND** selecting it MUST set `engine=qwen` in the run request
