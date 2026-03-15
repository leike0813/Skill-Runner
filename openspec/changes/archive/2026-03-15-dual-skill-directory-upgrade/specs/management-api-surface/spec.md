## ADDED Requirements

### Requirement: Skill management summary MUST expose builtin-source indicator
系统 MUST 在 Skill 管理摘要与复用该摘要语义的详情响应中返回 `is_builtin:boolean`，用于表达当前最终生效 skill 是否来自 `skills_builtin/`。

#### Scenario: Built-in skill reports true
- **GIVEN** 某 `skill_id` 仅存在于 `skills_builtin/`
- **WHEN** 客户端请求 Skill 管理列表或该 skill 详情
- **THEN** 响应中的 `is_builtin` 为 `true`

#### Scenario: User-provided skill reports false
- **GIVEN** 某 `skill_id` 仅存在于 `skills/`
- **WHEN** 客户端请求 Skill 管理列表或该 skill 详情
- **THEN** 响应中的 `is_builtin` 为 `false`

#### Scenario: User override of built-in reports false
- **GIVEN** 同一 `skill_id` 同时存在于 `skills_builtin/` 与 `skills/`
- **WHEN** 客户端请求 Skill 管理列表或该 skill 详情
- **THEN** 响应中的 `is_builtin` 为 `false`
- **AND** 对外返回的版本信息、入口信息与文件信息对应用户目录版本
