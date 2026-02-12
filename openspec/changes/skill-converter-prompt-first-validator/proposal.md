## Why

The current converter implementation is too script-heavy and underuses the LLM's semantic reasoning, which is the core requirement for reliable skill conversion decisions. We need to refactor it into a prompt-first Agent skill where `SKILL.md` drives conversion logic and scripts are limited to final contract validation.

## What Changes

- Refactor `skill-converter-agent` to a prompt-first architecture:
  - semantic analysis and conversion decisions are defined in `SKILL.md`
  - conversion execution is agent-led instead of script-led
- Remove conversion scripts that currently perform rule-based transformation logic.
- Keep only one final validation script in the skill package.
- Embed project-equivalent `SkillPackageValidator` logic inside the skill package so validation can run during agent skill execution without importing service internals.
- Preserve dual input usability (`directory` and `zip`) at instruction level, but enforce the same output contract.
- Keep output contract requirements:
  - complete install-ready skill package
  - bundled `references/file_protocol.md`
  - `SKILL.md` explicitly references `references/file_protocol.md`

## Capabilities

### New Capabilities
- `skill-converter-prompt-first`: Prompt-first converter behavior with LLM semantic classification and decision flow.

### Modified Capabilities
- None.

## Impact

- `skills/skill-converter-agent/SKILL.md` becomes the primary conversion logic contract.
- `skills/skill-converter-agent/scripts/` is reduced to one final validator script plus embedded validator module.
- Existing converter script tests are replaced by prompt-first flow and validator contract tests.
- Documentation for converter usage and validation behavior must be updated.

