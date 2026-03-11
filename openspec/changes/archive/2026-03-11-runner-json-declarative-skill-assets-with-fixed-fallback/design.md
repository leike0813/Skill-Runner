## Design

Introduce a shared skill asset resolver as the single source of truth for:

- `schemas.input`
- `schemas.parameter`
- `schemas.output`
- `engine_configs.{engine}`

Resolution order:

1. `runner.json` declared relative path
2. Existing fixed fallback filename
3. Asset-type-specific terminal behavior

The resolver performs:

- empty/invalid declaration detection
- skill-root boundary enforcement
- target existence checks
- fallback selection

Failure policy:

- Schemas:
  - invalid declaration -> warning + fallback
  - fallback missing -> error
- Engine config:
  - invalid declaration -> backend log only + fallback
  - fallback missing -> treated as absent skill defaults

`adapter_profile.config_assets.skill_defaults_path` remains, but only as the engine-defined fixed fallback filename.
