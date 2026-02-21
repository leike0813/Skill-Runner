## ADDED Requirements

### Requirement: Skill package 校验合同 MUST 以独立 schema 文件声明
系统 MUST 提供独立的 schema 文件来声明 skill package 与 `assets/runner.json` 的校验合同，而非仅依赖服务内硬编码规则。

#### Scenario: 校验入口加载独立 schema
- **WHEN** 系统启动安装或临时上传校验流程
- **THEN** 系统从独立 schema 文件加载并执行结构化校验
- **AND** 校验失败信息可映射为稳定的字段级错误

### Requirement: 安装与临时上传 MUST 复用同一 runner manifest 合同
系统 MUST 在持久安装与临时 skill 上传两条路径复用同一份 `runner.json` 合同 schema，保证行为一致。

#### Scenario: 两条路径对同一非法字段给出一致拒绝
- **WHEN** 同一个 `runner.json` 在 `engines`/`unsupported_engines` 字段违反合同
- **THEN** 安装与临时上传都拒绝该包
- **AND** 拒绝原因为同一类合同违规

### Requirement: runner engine 声明合同 MUST 支持“允许 + 排除”组合语义
`runner.json` 合同 MUST 支持 `engines`（可选）与 `unsupported_engines`（可选）联合声明，并满足：  
1) 两字段中的 engine 值必须来自系统支持引擎枚举；  
2) 两字段同时存在时不得有重复项；  
3) 缺失 `engines` 时，允许集合语义为“系统全量支持引擎”；  
4) 最终有效引擎集合 `effective_engines` 必须非空。

#### Scenario: 仅声明排除列表
- **WHEN** `runner.json` 省略 `engines` 且声明 `unsupported_engines`
- **THEN** 系统按“全量支持引擎减去排除列表”计算有效引擎集合
- **AND** 该包通过 engine 合同校验（前提是结果非空）

#### Scenario: 允许与排除声明重复
- **WHEN** `engines` 与 `unsupported_engines` 同时存在且包含重复 engine
- **THEN** 系统拒绝该 skill 包为合同无效

#### Scenario: 计算后无可用引擎
- **WHEN** `effective_engines` 计算结果为空
- **THEN** 系统拒绝该 skill 包并返回校验错误

### Requirement: input/parameter/output schema MUST 有服务端 meta-schema 预检
系统 MUST 对 `runner.json.schemas` 指向的 `input`、`parameter`、`output` schema 执行独立 meta-schema 校验，并在安装与临时上传两条链路统一生效。

#### Scenario: input schema 扩展键非法
- **WHEN** `input.schema.json` 中 `x-input-source` 使用未支持取值
- **THEN** 系统在上传校验阶段拒绝该 skill 包

#### Scenario: output schema artifact 扩展键非法
- **WHEN** `output.schema.json` 中 `x-type` 使用未支持取值
- **THEN** 系统在上传校验阶段拒绝该 skill 包

#### Scenario: parameter schema 基本结构非法
- **WHEN** `parameter.schema.json` 不满足服务端要求的对象 schema 基本结构
- **THEN** 系统在上传校验阶段拒绝该 skill 包
