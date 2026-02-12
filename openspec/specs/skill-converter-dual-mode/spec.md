# skill-converter-dual-mode Specification

## Purpose
TBD - created by archiving change skill-converter-dual-mode. Update Purpose after archive.
## Requirements
### Requirement: Converter supports directory source input
The converter SHALL accept a local skill directory as source input for interactive-first conversion workflows.

#### Scenario: Convert from local directory
- **WHEN** the user provides a valid local source skill directory
- **THEN** the converter analyzes and converts that directory without requiring source zip upload

### Requirement: Converter keeps zip source compatibility
The converter MUST continue to support zip source input for Skill-Runner compatible execution flows.

#### Scenario: Convert from zip source
- **WHEN** the user provides a valid source zip package
- **THEN** the converter executes conversion with the same core validation and generation rules

### Requirement: Dual modes share one conversion core
Directory mode and zip mode MUST use a shared conversion core so generated package semantics remain consistent.

#### Scenario: Shared core execution path
- **WHEN** conversion runs in either source mode
- **THEN** patching, schema generation, runner generation, and validation are performed by the same core logic

### Requirement: Output package contract parity across modes
For equivalent source skill content, directory mode and zip mode SHALL produce equivalent required contract files.

#### Scenario: Mode parity for contracts
- **WHEN** the same source skill content is converted via directory mode and zip mode
- **THEN** generated `assets/runner.json`, `assets/input.schema.json`, `assets/parameter.schema.json`, and `assets/output.schema.json` are equivalent in contract semantics

### Requirement: Converted package remains complete and install-ready
Both modes MUST produce a complete install-ready package including bundled protocol reference and conversion report.

#### Scenario: Complete package output
- **WHEN** conversion succeeds in either source mode
- **THEN** output includes converted skill directory, install-ready zip, `references/file_protocol.md`, and conversion report json

### Requirement: Patched SKILL.md references protocol guidance path
In both modes, patched `SKILL.md` MUST include explicit guidance to `references/file_protocol.md` for schema/runner generation questions.

#### Scenario: SKILL.md guidance path present
- **WHEN** conversion completes successfully
- **THEN** the converted `SKILL.md` contains an explicit reference to `references/file_protocol.md`

