## Why

We want users to upload and update Skill Runner supported skills directly via the API, without relying on other out-of-band methods.

## What Changes

- Add an async API workflow for installing or updating a skill from an uploaded zip package.
- Validate skill packages against the Runner AutoSkill Profile before installation.
- Enforce monotonically increasing skill versions; reject downgrades.
- Archive prior versions to `skills/.archive/<skill_id>/<version>/` on update.

## Capabilities

### New Capabilities
- `skill-package-install`: Upload and install/update a skill package via API with validation and version checks.
- `skill-package-archive`: Archive prior skill versions on update to `skills/.archive/`.

### Modified Capabilities
- `n/a`

## Impact

- New API endpoint(s) for skill package upload and installation.
- `SkillRegistry` will need to refresh/recognize newly installed skills.
- No changes to `WorkspaceManager` or `SchemaValidator` are required.
