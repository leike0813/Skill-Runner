## Why

Skill assets currently split into two inconsistent models:

- schema paths are declared in `runner.json.schemas`
- engine-specific skill config files still depend on adapter-level fixed filenames

This makes skill packaging and runtime resolution inconsistent, and it forces authors to know which assets are declarative and which are convention-only.

## What Changes

- Add `runner.json.engine_configs` as the declarative override entry for skill-specific engine config files.
- Unify schema and engine-config resolution under one resolver: declared path first, fixed filename fallback second.
- Keep existing fixed filenames as compatibility fallback.
- Differentiate failure policy:
  - schema fallback missing remains an error
  - engine-config fallback missing becomes "not provided"

## Impact

- Existing skills keep working without migration.
- Skill authors can override engine config asset paths from `runner.json`.
- Validation, patching, runtime execution, cache fingerprinting, and management UI all use the same resolution behavior.
