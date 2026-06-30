## ADDED Requirements

### Requirement: Release version MUST be managed through a single project version source

The system MUST use `pyproject.toml` `[project].version` as the backend version source and provide a script to update or verify that version.

#### Scenario: bumping backend version
- **WHEN** a maintainer runs `scripts/bump_version.py 0.7.3`
- **THEN** the script updates only `pyproject.toml` `[project].version` to `0.7.3`
- **AND** it does not create git tags
- **AND** it does not commit, switch branches, or modify git history

#### Scenario: tag release version check
- **WHEN** release CI runs for tag `v0.7.3`
- **THEN** it verifies `pyproject.toml` version is `0.7.3`
- **AND** it fails before publishing release assets if the values differ

#### Scenario: invalid version is rejected
- **WHEN** a maintainer provides a non-SemVer value
- **THEN** the bump script exits non-zero
- **AND** it does not update project version
