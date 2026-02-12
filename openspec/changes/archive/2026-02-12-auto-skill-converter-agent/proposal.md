## Why

Current users who have an existing generic agent skill still need to manually adapt it into the Skill Runner AutoSkill profile before it can run reliably in this service. We need a guided, automatable conversion capability so users can quickly onboard third-party or legacy skills with consistent contracts.

## What Changes

- Add a new Agent skill that converts an existing skill package into a Skill Runner compatible AutoSkill package.
- The converter patches `SKILL.md` with Skill Runner-oriented execution instructions and default behavior conventions.
- The converter generates required execution contracts under `assets/`, including schema files and `runner.json`.
- The converter outputs a complete validated skill package structure ready for API installation and runtime execution.
- The converter includes `references/file_protocol.md` in the generated package as a reference for schema and `runner.json` conventions.
- The converter updates `SKILL.md` to explicitly point to `references/file_protocol.md` when schema generation decisions are unclear.
- Add validation and failure reporting for unsupported or incomplete input skill structures.

## Capabilities

### New Capabilities
- `skill-converter-agent`: Convert a generic skill package into a Skill Runner AutoSkill package by patching `SKILL.md` and generating required `assets` contracts.

### Modified Capabilities
- None.

## Impact

- New skill assets and templates for conversion rules (prompt patch policy, default behavior policy, schema scaffolding rules).
- New test coverage for conversion success and failure paths (missing metadata, invalid identity, unsupported layouts).
- Documentation updates for usage flow: input package expectations, conversion output structure, and integration with `/v1/skill-packages/install`.
