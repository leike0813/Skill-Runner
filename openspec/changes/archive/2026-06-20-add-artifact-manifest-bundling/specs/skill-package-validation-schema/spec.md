## MODIFIED Requirements

### Requirement: input/parameter/output schema MUST 有服务端 meta-schema 预检
系统 MUST 对 `runner.json.schemas` 指向的 `input`、`parameter`、`output` schema 执行独立 meta-schema 校验，并在安装与临时上传两条链路统一生效。`output.schema.json` 中 `x-type: "artifact"` 字段 MUST declare a non-empty `x-role`; the reserved `x-role: "artifact-manifest"` declares a generated artifact manifest.

#### Scenario: output schema artifact 扩展键非法
- **WHEN** `output.schema.json` 中 `x-type` 使用未支持取值
- **THEN** 系统在上传校验阶段拒绝该 skill 包

#### Scenario: artifact field missing role is rejected
- **WHEN** `output.schema.json` contains a field with `x-type: "artifact"` but no non-empty `x-role`
- **THEN** 系统在上传校验阶段拒绝该 skill 包

#### Scenario: artifact manifest role passes validation
- **WHEN** `output.schema.json` contains a string field with `x-type: "artifact"` and `x-role: "artifact-manifest"`
- **THEN** 系统在上传校验阶段接受该 output schema

