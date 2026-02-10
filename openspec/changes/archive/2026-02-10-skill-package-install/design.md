## Context

Skill Runner currently discovers skills by scanning the `skills/` directory and loading `assets/runner.json` plus schemas. There is no API for installing or updating skills. We need an async, server-side install workflow that validates packages against the AutoSkill Profile and supports versioned updates with archival of prior versions.

Constraints and decisions from requirements:
- Skill packages are uploaded as zip files and must contain a single top-level directory named `skill_id`.
- Validation must follow the AutoSkill Profile (see `docs/dev_guide.md`).
- Updates must be monotonically increasing; downgrades are rejected.
- Prior versions are archived under `skills/.archive/<skill_id>/<version>/`.
- The install workflow must be asynchronous.

## Goals / Non-Goals

**Goals:**
- Provide an async API to upload and install/update skills from zip packages.
- Validate package structure and required files strictly before installation.
- Enforce monotonic versioning and archive previous versions on updates.
- Refresh the skill registry after successful install/update.

**Non-Goals:**
- Implement a remote skill registry or marketplace.
- Support partial/incremental updates inside a skill package.
- Provide backward compatibility for invalid or legacy skill layouts.

## Decisions

### Decision 1: Introduce a dedicated skill package install service
Use a new service (e.g. `skill_package_manager`) that handles validation, staging, installation, and archival. This keeps install logic separate from run orchestration and avoids entangling with `WorkspaceManager` or `SchemaValidator` logic.

**Rationale:** Install/update is a different lifecycle from job execution and should not reuse run workspace semantics.

### Decision 2: Use a new install status store
Create a lightweight store for install jobs (e.g. `data/skill_installs.db`) with fields: `request_id`, `skill_id`, `version`, `status`, `error`, `created_at`, `updated_at`.

**Rationale:** Reusing `runs.db` would mix different lifecycles and complicate queries. A separate store keeps concerns clear.

### Decision 3: Stage, validate, then swap
Unpack the zip into a staging directory under `skills/.staging/<request_id>/`. Perform all validation against the staged content. Only after validation passes do we update the live `skills/<skill_id>` directory. On update, move existing `skills/<skill_id>` to `skills/.archive/<skill_id>/<old_version>/` first, then move staged content into place.

**Rationale:** This preserves atomicity and avoids partial installs. Validation failures never touch the live skill directory.

### Decision 4: Version comparison via strict parse
Require `assets/runner.json` to contain a version string parseable by `packaging.version.Version`. Reject missing or unparseable versions. Reject updates where `new_version <= old_version`.

**Rationale:** Ensures monotonic behavior without ambiguous string comparison.

### Decision 5: Archive path is immutable
If `skills/.archive/<skill_id>/<old_version>/` already exists, the update is rejected. No overwrites are allowed.

**Rationale:** Avoids silent data loss in archive history.

### Decision 6: Async API using background tasks
The install endpoint will immediately create an install job (status `queued`) and return the `request_id`. A background task executes validation and install, updating status to `succeeded` or `failed`.

**Rationale:** Skill packages can be large and processing can be slow; async fits existing server patterns.

## Risks / Trade-offs

- **[Multi-process race]** If multiple workers install/update the same skill concurrently → Mitigation: use a per-skill lock file (best-effort) and serialize updates within the process.
- **[Archive failure]** Insufficient permissions for archive directory → Mitigation: fail update before moving live skill, return explicit error.
- **[Registry staleness]** SkillRegistry caches old entries → Mitigation: explicitly call `skill_registry.scan_skills()` after a successful install.

## Migration Plan

- Add new endpoint(s) and service classes without modifying existing run/job APIs.
- No data migration required; new store starts empty.
- Rollback: disable new endpoint(s); existing skills remain untouched.

## Open Questions

- Whether to expose detailed validation errors in the install status response or only a summarized error message.
- Whether to allow a “force install” mode for development (currently out of scope).
