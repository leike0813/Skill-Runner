# skill-package-archive Specification

## Purpose
定义 skill 更新时旧版本归档的路径唯一性和归档策略。

## MODIFIED Requirements

### Requirement: Archive prior skill version on update
When installing a new version of an existing skill, the system MUST archive the current version to `skills/.archive/<skill_id>/<version>/` before replacing it.

#### Scenario: Archive on update
- **WHEN** a valid update with a higher version is installed
- **THEN** the existing skill directory is moved to `skills/.archive/<skill_id>/<old_version>/`
