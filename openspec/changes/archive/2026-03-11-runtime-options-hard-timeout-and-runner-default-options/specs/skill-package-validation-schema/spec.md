## MODIFIED Requirements

### Requirement: Skill package 校验合同 MUST 以独立 schema 文件声明
系统 MUST 提供独立的 schema 文件来声明 skill package 与 `assets/runner.json` 的校验合同，而非仅依赖服务内硬编码规则。

#### Scenario: runner manifest 支持 runtime 默认选项声明
- **WHEN** `runner.json` 包含 `runtime.default_options` 对象
- **THEN** 合同校验 MUST 允许该字段通过
- **AND** 其值用于运行时默认 option 合成

#### Scenario: runtime 默认选项声明缺失
- **WHEN** `runner.json` 未声明 `runtime.default_options`
- **THEN** skill 包校验保持通过
- **AND** 系统仅使用请求侧 runtime options
