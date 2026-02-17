## ADDED Requirements

### Requirement: Skill runner.json MUST 声明允许的执行模式
系统 MUST 支持 Skill 在 `assets/runner.json` 中通过 `execution_modes` 声明其允许的执行模式。

#### Scenario: 合法声明
- **WHEN** Skill 包在 `runner.json` 中声明 `execution_modes`
- **THEN** 该字段是非空数组
- **AND** 每个值都属于 `auto` 或 `interactive`

#### Scenario: 缺失或非法声明
- **WHEN** `execution_modes` 缺失、为空或包含非法值
- **THEN** 新上传/更新的 Skill 包校验失败

### Requirement: 系统 MUST 对存量缺失声明 Skill 提供 auto 兼容
为避免一次性破坏已安装旧 Skill，系统 MUST 在兼容期内将缺失声明的存量 Skill 解释为 `["auto"]`。

#### Scenario: 存量 skill 缺失 execution_modes
- **GIVEN** Skill 已安装且 `runner.json` 缺失 `execution_modes`
- **WHEN** 客户端提交 `execution_mode=auto`
- **THEN** 系统允许执行
- **AND** 记录 deprecation 告警，提示补齐声明
