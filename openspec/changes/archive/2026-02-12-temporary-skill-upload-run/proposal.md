## Why

We need a way for users to run one-off skills without installing them into the persistent `skills/` registry. This enables fast experimentation and task-specific automation via API while keeping long-term skill storage clean.

## What Changes

- Add a new API workflow to upload a temporary skill package and submit a run against it.
- Validate temporary skill packages with the same Runner AutoSkill Profile constraints used for normal skills.
- Execute runs using the validated temporary skill in an isolated temporary location.
- Automatically clean up temporary skill files after run completion (success or failure).
- Keep persistent skill installation (`/v1/skill-packages/install`) and temporary execution workflows separate.

## Capabilities

### New Capabilities
- `ephemeral-skill-upload-and-run`: Upload a temporary skill package and execute a job against it via API.
- `ephemeral-skill-validation`: Enforce strict temporary skill package validation before execution.
- `ephemeral-skill-lifecycle`: Manage temporary skill lifecycle with automatic cleanup after run completion.

### Modified Capabilities
- `n/a`

## Impact

- New API endpoint(s) for temporary skill upload + run submission and temporary request/status tracking.
- Run orchestration path will support a temporary skill source in addition to registry-based skills.
- `SkillRegistry` behavior remains unchanged for persistent discovery, but execution resolution will need a temporary-skill branch.
- `WorkspaceManager` may need extensions for temporary skill staging and cleanup hooks.
