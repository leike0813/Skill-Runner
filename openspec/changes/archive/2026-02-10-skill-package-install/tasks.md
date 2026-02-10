## 1. Data Model and Store

- [x] 1.1 Add install job model (request id, skill id, version, status, error, timestamps)
- [x] 1.2 Implement a lightweight install status store (sqlite) with create/update/get/list helpers

## 2. Package Validation and Staging

- [x] 2.1 Implement zip inspection and staging extraction under `skills/.staging/<request_id>/`
- [x] 2.2 Validate package structure (single top-level directory = skill_id)
- [x] 2.3 Validate AutoSkill Profile requirements (`SKILL.md`, `assets/runner.json`, `assets/input.schema.json`, `assets/output.schema.json`)
- [x] 2.4 Validate identity consistency (directory name, runner.json id, SKILL.md frontmatter name)
- [x] 2.5 Validate `engines` and `artifacts` in runner.json
- [x] 2.6 Validate version parseability and enforce monotonic updates

## 3. Install/Update and Archive Flow

- [x] 3.1 Implement archive-on-update to `skills/.archive/<skill_id>/<old_version>/` with no overwrite
- [x] 3.2 Implement atomic swap from staging to live `skills/<skill_id>`
- [x] 3.3 Refresh `SkillRegistry` after successful install/update

## 4. API and Async Execution

- [x] 4.1 Add install endpoint to accept zip uploads and create async install jobs
- [x] 4.2 Add install status endpoint for querying job state and error details
- [x] 4.3 Wire background execution to update install status on success/failure

## 5. Tests and Docs

- [x] 5.1 Unit tests for validator edge cases (missing files, id mismatch, downgrade)
- [x] 5.2 Unit tests for archive behavior and atomic update paths
- [x] 5.3 API tests for install and status endpoints
- [x] 5.4 Document the new API and package requirements
