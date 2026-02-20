## ADDED Requirements

### Requirement: 系统 MUST 校验请求引擎是否被 Skill 允许
系统 MUST 在 run 创建阶段基于 Skill 的 `effective_engines` 校验请求引擎是否允许执行。

#### Scenario: 请求引擎在有效集合内
- **GIVEN** Skill 的 `effective_engines` 包含请求引擎
- **WHEN** 客户端提交创建 run 请求
- **THEN** 系统接受请求并进入后续执行流程

#### Scenario: 请求命中显式不支持引擎
- **GIVEN** Skill 在 `runner.json.unsupport_engine` 中声明了请求引擎
- **WHEN** 客户端提交创建 run 请求
- **THEN** 系统返回 `400`
- **AND** 错误码为 `SKILL_ENGINE_UNSUPPORTED`

#### Scenario: 请求引擎不在允许集合
- **GIVEN** Skill 显式声明 `runner.json.engines` 且请求引擎不在该集合（或被排除后不在 `effective_engines`）
- **WHEN** 客户端提交创建 run 请求
- **THEN** 系统返回 `400`
- **AND** 错误码为 `SKILL_ENGINE_UNSUPPORTED`
