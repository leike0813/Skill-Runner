# ephemeral-skill-validation Specification

## Purpose
定义临时 skill 包结构和 AutoSkill 必需文件的校验规则。

## MODIFIED Requirements

### Requirement: Temporary skill package structure is mandatory
The system MUST require temporary skill packages to contain exactly one top-level directory and treat that directory name as the temporary `skill_id`.

#### Scenario: Reject invalid top-level layout
- **WHEN** an uploaded temporary skill package has zero or multiple top-level directories
- **THEN** the system rejects the request as invalid
