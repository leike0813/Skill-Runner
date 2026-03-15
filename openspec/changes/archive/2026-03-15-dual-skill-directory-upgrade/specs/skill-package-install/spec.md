## ADDED Requirements

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
