# ephemeral-skill-validation Specification

## Purpose
TBD - created by archiving change temporary-skill-upload-run. Update Purpose after archive.
## Requirements
### Requirement: Temporary skill package structure is mandatory
The system MUST require temporary skill packages to contain exactly one top-level directory and treat that directory name as the temporary `skill_id`.

#### Scenario: Reject invalid top-level layout
- **WHEN** an uploaded temporary skill package has zero or multiple top-level directories
- **THEN** the system rejects the request as invalid

### Requirement: AutoSkill required files must be present for temporary skills
The system MUST require temporary skill packages to include `SKILL.md`, `assets/runner.json`, and all schema files referenced by `runner.json.schemas` (`input`, `parameter`, `output`).

#### Scenario: Reject missing required file
- **WHEN** a temporary skill package is missing any required file
- **THEN** the system rejects the request as invalid

### Requirement: Temporary skill identity fields must match
The system MUST enforce identity consistency across temporary skill directory name, `runner.json.id`, and `SKILL.md` frontmatter `name`.

#### Scenario: Reject identity mismatch
- **WHEN** any temporary skill identity field does not match the others
- **THEN** the system rejects the request as invalid

### Requirement: Temporary skill metadata must satisfy execution constraints
The system MUST validate temporary skill engine declarations with the same contract as persistent installs:
- `engines` MAY be omitted;
- `unsupported_engines` MAY be declared to explicitly deny engines;
- when both are present, they MUST NOT overlap;
- `effective_engines = (engines if provided else all system-supported engines) - unsupported_engines`;
- `effective_engines` MUST be non-empty;
- `artifacts` contract requirements remain unchanged.

#### Scenario: Temporary skill omits engines with valid artifacts
- **WHEN** temporary `runner.json` omits `engines` and declares valid `artifacts`
- **THEN** the system computes `effective_engines` from all system-supported engines minus `unsupported_engines`
- **AND** the temporary package passes metadata validation when result is non-empty

#### Scenario: Temporary skill declares overlapping allow/deny engines
- **WHEN** temporary `runner.json` contains the same engine in both `engines` and `unsupported_engines`
- **THEN** the system rejects the upload request as invalid

#### Scenario: Temporary skill yields empty effective engines
- **WHEN** temporary `runner.json` engine declarations produce an empty `effective_engines`
- **THEN** the system rejects the upload request as invalid

### Requirement: Temporary skill upload must enforce package size limit
The system MUST enforce a configurable package size limit for temporary skill uploads.

#### Scenario: Reject oversized temporary skill package
- **WHEN** the uploaded temporary skill package exceeds configured size limit
- **THEN** the system rejects the request as invalid

### Requirement: Zip extraction must be path-safe
The system MUST reject zip entries that attempt unsafe path traversal or absolute-path extraction.

#### Scenario: Reject zip-slip entry
- **WHEN** a temporary skill package contains `..` or absolute-path zip entries
- **THEN** the system rejects the request as invalid

### Requirement: 临时 Skill 校验 MUST 包含 execution_modes 声明
系统 MUST 在临时 skill 上传校验中要求 `runner.json.execution_modes` 为合法声明。

#### Scenario: 临时包声明 execution_modes
- **WHEN** 客户端上传临时 skill 包
- **THEN** 系统校验 `execution_modes` 为非空且仅包含 `auto|interactive`

#### Scenario: 临时包缺失 execution_modes
- **WHEN** 临时 skill 包缺失 `execution_modes` 或声明非法值
- **THEN** 系统拒绝该上传请求并返回校验错误

