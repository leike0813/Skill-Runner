# skill-converter-agent Specification

## Purpose
TBD - created by archiving change auto-skill-converter-agent. Update Purpose after archive.
## Requirements
### Requirement: Converter skill accepts an existing generic skill package as input
The converter skill SHALL accept a source skill package and use it as the input for conversion.

#### Scenario: Convert from provided source package
- **WHEN** the user provides a valid source skill package path or archive
- **THEN** the converter loads that package and starts conversion analysis

### Requirement: Converter skill supports interactive decision flow
The converter skill MUST support interactive questions during conversion when source information is ambiguous or incomplete.

#### Scenario: Ask user for unresolved metadata
- **WHEN** the converter cannot determine required metadata from source files
- **THEN** it asks the user targeted questions and continues after receiving decisions

### Requirement: Converter skill supports optional non-interactive mode
The converter skill SHALL support a non-interactive mode for batch usage when all required decisions are preconfigured.

#### Scenario: Run conversion without prompts
- **WHEN** conversion is invoked with complete policy/default inputs
- **THEN** the converter completes without requesting user interaction

### Requirement: Converter patches SKILL.md for Skill Runner execution contract
The converter skill MUST patch or append `SKILL.md` with an explicit Skill Runner execution contract while preserving original domain intent.

#### Scenario: Add execution contract block
- **WHEN** source `SKILL.md` lacks Skill Runner-specific execution contract instructions
- **THEN** the converter writes a contract block that defines execution assumptions, output conventions, and failure handling

### Requirement: SKILL.md must reference local protocol guidance
The converter skill MUST ensure `SKILL.md` explicitly references `references/file_protocol.md` as guidance when schema or runner contract generation details are uncertain.

#### Scenario: Add protocol reference hint into SKILL.md
- **WHEN** converter patches or rewrites guidance sections in `SKILL.md`
- **THEN** the final `SKILL.md` includes a clear pointer to `references/file_protocol.md`

### Requirement: Converter generates required AutoSkill assets
The converter skill MUST generate Skill Runner required assets including `assets/runner.json`, `assets/input.schema.json`, `assets/parameter.schema.json`, and `assets/output.schema.json`.

#### Scenario: Generate missing required files
- **WHEN** any required AutoSkill asset file is missing in source package
- **THEN** the converter generates the missing file with valid baseline structure

### Requirement: Converter enforces identity consistency in output package
The converter skill MUST enforce that output package directory name, `assets/runner.json.id`, and `SKILL.md` frontmatter `name` are identical.

#### Scenario: Resolve identity mismatch
- **WHEN** source package contains inconsistent identity values
- **THEN** the converter applies selected identity policy and emits a warning describing the normalization

### Requirement: Converter validates output package against install-time rules
The converter skill MUST validate converted output against the same structural rules required by Skill Runner skill-package installation.

#### Scenario: Reject non-installable conversion output
- **WHEN** converted output violates required structure or contract constraints
- **THEN** conversion is marked failed with actionable validation errors

### Requirement: Converter emits structured conversion report
The converter skill MUST emit a machine-readable conversion report describing generated files, patched files, warnings, and blocking errors.

#### Scenario: Produce conversion_report.json
- **WHEN** conversion completes (success or failure)
- **THEN** a structured report file is generated with actions and diagnostics

### Requirement: Converter outputs install-ready package layout
The converter skill SHALL output a package layout directly consumable by `/v1/skill-packages/install`.

#### Scenario: Use converter output for installation
- **WHEN** conversion succeeds
- **THEN** the resulting package can be submitted to install API without additional mandatory file creation

### Requirement: Converter includes protocol reference document in generated package
The converter skill MUST include `references/file_protocol.md` in the generated output package as a reference for maintaining generated schema and runner contracts.

#### Scenario: Bundle protocol reference
- **WHEN** conversion succeeds
- **THEN** output package contains `references/file_protocol.md` with the project reference content

