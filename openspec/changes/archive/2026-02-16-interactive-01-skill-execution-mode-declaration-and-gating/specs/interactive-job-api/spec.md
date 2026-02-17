## ADDED Requirements

### Requirement: 系统 MUST 校验请求执行模式是否被 Skill 允许
系统 MUST 在 run 创建阶段校验 `execution_mode` 是否属于 Skill 声明的 `execution_modes`。

#### Scenario: 请求模式被 Skill 允许
- **GIVEN** Skill 声明 `execution_modes` 包含请求模式
- **WHEN** 客户端提交创建 run 请求
- **THEN** 系统接受请求并进入后续执行流程

#### Scenario: 请求模式不被 Skill 允许
- **GIVEN** Skill 声明 `execution_modes` 不包含请求模式
- **WHEN** 客户端提交创建 run 请求
- **THEN** 系统返回 `400`
- **AND** 错误码为 `SKILL_EXECUTION_MODE_UNSUPPORTED`
