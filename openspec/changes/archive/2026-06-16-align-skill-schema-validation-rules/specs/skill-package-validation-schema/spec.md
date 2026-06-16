## MODIFIED Requirements

### Requirement: input/parameter/output schema MUST 有服务端 meta-schema 预检
系统 MUST 对所有解析到文件的 `input`、`parameter`、`output` schema 执行独立 meta-schema 校验，并在安装与临时上传两条链路统一生效。`output` schema MUST be resolvable; `input` and `parameter` schemas MAY be absent.

#### Scenario: input schema 扩展键非法
- **WHEN** `input.schema.json` is present and `x-input-source` uses an unsupported value
- **THEN** 系统在上传校验阶段拒绝该 skill 包

#### Scenario: output schema artifact 扩展键非法
- **WHEN** `output.schema.json` 中 `x-type` 使用未支持取值
- **THEN** 系统在上传校验阶段拒绝该 skill 包

#### Scenario: parameter schema 基本结构非法
- **WHEN** `parameter.schema.json` is present and does not satisfy the service object-schema shape
- **THEN** 系统在上传校验阶段拒绝该 skill 包

#### Scenario: optional schema absent
- **WHEN** `input` or `parameter` schema cannot be resolved
- **THEN** validation MUST accept the skill package
- **AND** runtime MUST treat that schema as absent

#### Scenario: required output schema absent
- **WHEN** `output` schema cannot be resolved
- **THEN** validation MUST reject the skill package

### Requirement: runner.json asset declarations MUST support canonical fallback filenames
Skill package validation MUST accept omitted or misdeclared schema asset paths in `runner.json` when canonical fallback filenames are present and resolvable within the skill root. Missing `input` and `parameter` fallbacks MUST NOT reject the package.

#### Scenario: schema declaration missing but fallback exists
- **GIVEN** `runner.json.schemas.output` is missing
- **AND** `assets/output.schema.json` exists
- **THEN** validation MUST accept the skill package

#### Scenario: schema declaration invalid and fallback exists
- **GIVEN** `runner.json.schemas.input` is empty, invalid, escapes the skill root, or points to a missing file
- **AND** `assets/input.schema.json` exists
- **THEN** validation MUST accept the skill package
- **AND** validation MUST emit a warning

#### Scenario: optional schema declaration unresolved and fallback missing
- **GIVEN** `runner.json.schemas.parameter` cannot be resolved
- **AND** `assets/parameter.schema.json` does not exist
- **THEN** validation MUST accept the skill package
- **AND** validation MUST emit a warning

#### Scenario: output schema declaration unresolved and fallback missing
- **GIVEN** `runner.json.schemas.output` cannot be resolved
- **AND** `assets/output.schema.json` does not exist
- **THEN** validation MUST reject the skill package
