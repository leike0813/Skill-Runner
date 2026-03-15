# skill-package-install Specification

## Purpose
定义 skill 包上传、根目录校验和异步安装的 API 约束。
## Requirements
### Requirement: Accept skill package upload for async install
The system SHALL provide an API endpoint to accept a skill package as a zip upload and initiate an asynchronous installation job.

#### Scenario: Create an async install job
- **WHEN** a client uploads a zip package to the skill-install endpoint
- **THEN** the system returns a unique install request identifier and initial status

### Requirement: Skill package root directory is required
A skill package MUST contain exactly one top-level directory, and its name SHALL be treated as the `skill_id`.

#### Scenario: Missing or ambiguous top-level directory
- **WHEN** the uploaded zip does not contain exactly one top-level directory
- **THEN** the system rejects the package as invalid

### Requirement: Enforce AutoSkill Profile validation
The system MUST validate the uploaded skill package against the Runner AutoSkill Profile before installation.

#### Scenario: Missing required structural files
- **WHEN** the package is missing any required structural file (`SKILL.md`, `assets/runner.json`)
- **THEN** the system rejects the package as invalid

#### Scenario: Schema assets must be resolvable
- **WHEN** one or more schema assets are omitted from `runner.json.schemas`
- **AND** the corresponding canonical fallback files exist under `assets/`
- **THEN** the system accepts the package
- **AND** validation resolves those schemas via declaration-plus-fallback behavior

#### Scenario: Schema declaration and fallback both missing
- **WHEN** a required schema asset cannot be resolved from `runner.json.schemas`
- **AND** the corresponding canonical fallback file does not exist
- **THEN** the system rejects the package as invalid

### Requirement: Enforce identity consistency
The system MUST enforce that the skill directory name, `assets/runner.json` `id`, and `SKILL.md` frontmatter `name` are identical.

#### Scenario: ID mismatch
- **WHEN** any of the three identifiers do not match
- **THEN** the system rejects the package as invalid

### Requirement: Enforce engine declaration
The system MUST validate engine compatibility declarations in `assets/runner.json` using combined allow/deny semantics:
- `engines` MAY be omitted;
- `unsupported_engines` MAY be declared to explicitly deny engines;
- when both are present, they MUST NOT overlap;
- `effective_engines = (engines if provided else all system-supported engines) - unsupported_engines`;
- `effective_engines` MUST be non-empty.

#### Scenario: Engines omitted and deny-list omitted
- **WHEN** `assets/runner.json` omits both `engines` and `unsupported_engines`
- **THEN** the system treats the skill as allowing all system-supported engines
- **AND** the package passes engine contract validation

#### Scenario: Explicit allow-list with deny-list
- **WHEN** `assets/runner.json` declares non-empty `engines` and optional `unsupported_engines` without overlap
- **THEN** the system computes `effective_engines` from allow-list minus deny-list
- **AND** the package passes engine contract validation when `effective_engines` is non-empty

#### Scenario: Allow-list overlaps deny-list
- **WHEN** `assets/runner.json` declares `engines` and `unsupported_engines` with duplicated engine entries
- **THEN** the system rejects the package as invalid

#### Scenario: Effective engines becomes empty
- **WHEN** the computed `effective_engines` is empty after applying `unsupported_engines`
- **THEN** the system rejects the package as invalid

### Requirement: Enforce artifacts contract
The system MUST require `assets/runner.json` to declare an artifacts contract suitable for Runner indexing.

#### Scenario: Missing artifacts contract
- **WHEN** `assets/runner.json` omits `artifacts` or declares an empty list
- **THEN** the system rejects the package as invalid

### Requirement: Enforce version presence and monotonic updates
The system MUST require `assets/runner.json` to include a version string, and updates MUST be rejected if the new version is not strictly greater than the installed version.

#### Scenario: Downgrade or equal version
- **WHEN** a package is uploaded for an existing skill and its version is less than or equal to the installed version
- **THEN** the system rejects the update

### Requirement: Preserve existing skill on validation failure
The system MUST NOT modify or archive an existing skill if the uploaded package fails validation.

#### Scenario: Validation failure for existing skill
- **WHEN** an update package fails validation
- **THEN** the existing skill remains unchanged and no archive is created

### Requirement: Refresh skill registry after successful install
After a successful install or update, the system SHALL make the skill available to discovery without requiring a server restart.

#### Scenario: Post-install discovery
- **WHEN** an install job completes successfully
- **THEN** the skill appears in skill discovery results

### Requirement: Treat invalid existing skill directory as fresh install candidate
The install workflow MUST determine whether an existing skill directory is a valid installed skill by reading `assets/runner.json` and parsing a valid version.

#### Scenario: Existing directory missing runner metadata
- **GIVEN** `skills/<skill_id>/` exists
- **AND** `assets/runner.json` is missing or invalid
- **WHEN** a package for the same `skill_id` is uploaded
- **THEN** the system MUST NOT enter update flow
- **AND** MUST quarantine the existing directory into `skills/.invalid/`
- **AND** MUST proceed as a fresh install

### Requirement: Installed skill package MUST strip Git metadata
系统 MUST 在 skill package 安装流程中移除技能包内的 Git 元数据，避免与父仓库产生冲突。

#### Scenario: Fresh install strips `.git` directory
- **GIVEN** 上传的 skill package 已通过结构与版本校验
- **AND** 包内容包含 `.git/` 目录
- **WHEN** 系统执行安装
- **THEN** 最终 `skills/<skill_id>/` 目录中不包含 `.git/`
- **AND** 安装仍按正常流程完成

#### Scenario: Update install strips `.git` file
- **GIVEN** 已存在可更新的 `skills/<skill_id>/`
- **AND** 新上传包包含 `.git` 普通文件
- **WHEN** 系统执行更新安装
- **THEN** 更新后的 `skills/<skill_id>/` 中不包含 `.git` 文件
- **AND** 旧版本归档流程保持不变

#### Scenario: Non-git hidden files are preserved
- **GIVEN** 上传包中包含 `.gitignore`、`.github/` 等非 `.git` 名称文件或目录
- **WHEN** 系统执行安装或更新
- **THEN** 系统仅清理名称精确为 `.git` 的文件或目录
- **AND** 其他隐藏文件不因该策略被删除

### Requirement: 安装校验 MUST 包含 execution_modes 声明
系统 MUST 在 skill 包安装/更新校验中要求 `runner.json.execution_modes` 为合法声明。

#### Scenario: 安装包声明 execution_modes
- **WHEN** 上传 skill 包用于安装或更新
- **THEN** 系统校验 `execution_modes` 为非空且值在 `auto|interactive` 枚举内

#### Scenario: 安装包缺失 execution_modes
- **WHEN** 上传包缺失 `execution_modes` 或声明非法值
- **THEN** 系统拒绝安装并返回校验错误

### Requirement: Skill registry MUST support dual root resolution with user-precedence override
系统 MUST 使用双目录解析 skill：内建目录 `skills_builtin/` 与用户目录 `skills/`。  
当两个目录存在同一 `skill_id` 时，系统 MUST 选择用户目录版本作为最终生效 skill。

#### Scenario: Built-in skill is discoverable without user directory entry
- **GIVEN** `skills_builtin/<skill_id>/` 存在
- **AND** `skills/<skill_id>/` 不存在
- **WHEN** 系统进行 skill 注册扫描
- **THEN** 该 `skill_id` 出现在可发现列表中
- **AND** 最终生效来源为 `skills_builtin/`

#### Scenario: User skill overrides built-in skill with same id
- **GIVEN** `skills_builtin/<skill_id>/` 与 `skills/<skill_id>/` 同时存在
- **WHEN** 系统进行 skill 注册扫描
- **THEN** 该 `skill_id` 仅以单条记录对外暴露
- **AND** 最终生效来源为 `skills/<skill_id>/`

### Requirement: Skill package install workflow MUST write only into user skill root
系统 MUST 将 skill 包安装、更新、归档与异常隔离（如 invalid/staging）限定在用户目录 `skills/` 侧，MUST NOT 写入 `skills_builtin/`。

#### Scenario: Fresh install writes into user skill root
- **WHEN** 客户端安装新的 `skill_id`
- **THEN** 系统在 `skills/<skill_id>/` 落地安装结果
- **AND** 不在 `skills_builtin/` 下创建或修改该目录

#### Scenario: Update archives old user version under user archive tree
- **GIVEN** `skills/<skill_id>/` 已安装旧版本
- **WHEN** 客户端安装更高版本更新包
- **THEN** 旧版本归档到 `skills/.archive/<skill_id>/<version>/`
- **AND** 更新后的生效目录仍为 `skills/<skill_id>/`

#### Scenario: Built-in skill id conflict does not mutate built-in root
- **GIVEN** `skills_builtin/<skill_id>/` 已存在
- **WHEN** 客户端安装同 `skill_id` 的用户 skill
- **THEN** 系统仅在 `skills/<skill_id>/` 写入安装结果
- **AND** `skills_builtin/<skill_id>/` 保持不变

