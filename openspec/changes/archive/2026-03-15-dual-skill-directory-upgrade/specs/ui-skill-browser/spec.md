## ADDED Requirements

### Requirement: Management skills table MUST render built-in badge from `is_builtin`
管理 UI 首页 Skill 表格与 `/ui/management/skills/table` MUST 基于 management API 返回的 `is_builtin` 渲染内建标识，不得在前端自行推断目录来源。

#### Scenario: Built-in badge is shown for effective built-in skill
- **GIVEN** 某 `skill_id` 的管理摘要 `is_builtin=true`
- **WHEN** 页面渲染该 skill 行
- **THEN** 该行显示“Built-in/内建”标识

#### Scenario: Built-in badge disappears when user override is effective
- **GIVEN** 某 `skill_id` 同时存在内建与用户目录
- **AND** 管理摘要返回 `is_builtin=false`
- **WHEN** 页面渲染该 skill 行
- **THEN** 该行不显示“Built-in/内建”标识
