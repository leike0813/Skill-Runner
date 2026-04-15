## Why

The current prompt-builder contract still carries configuration for multiple legacy body-prompt strategies that are no longer aligned with the newer run-root instructions and invoke-line model. Per-engine default templates are mostly duplicated, adapter profiles still expose obsolete compatibility fields, and prompt context generation keeps injecting variables that the new prompt model no longer wants to support.

## What Changes

- Collapse the default body prompt to one shared template.
- Replace per-engine default template selection with optional profile-level prefix/suffix extra blocks.
- Remove prompt-builder compatibility fields for `parameter.prompt`, `params_json`, `skill_dir`, `input_file`, and related fallback wiring.
- Keep skill-specific `entrypoint.prompts[engine/common]` as the highest-priority full body override.
- Update docs, fixtures, and tests to the new breaking prompt-builder profile shape.

## Capabilities

### Modified Capabilities
- `engine-adapter-runtime-contract`: prompt assembly now uses a single shared default body template plus optional profile extra blocks, and adapter profiles no longer declare legacy prompt-body compatibility switches.
- `skill-patch-modular-injection`: prompt-organization docs and runtime contract now align on invoke-line plus body-only prompt assembly without legacy prompt-builder context injection.
- `run-audit-contract`: prompt audit continues to record only the assembled skill prompt, now built from the simplified profile contract.

## Impact

- Affected code: adapter profile schema/loader, common prompt builder, engine adapter profiles, and a small set of fixture prompts/tests.
- Affected docs: prompt organization SSOT, adapter profile reference, engine onboarding example.
- Affected tests: adapter profile loader, prompt builder common tests, and related auth-detection profile fixture coverage.
