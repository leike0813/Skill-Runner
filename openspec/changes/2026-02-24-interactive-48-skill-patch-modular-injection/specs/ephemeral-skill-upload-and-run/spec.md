## MODIFIED Requirements

### Requirement: 临时 skill 运行路径 MUST 使用统一 patch 能力
系统 MUST 在临时运行与常规运行中复用同一 `SkillPatcher` 注入逻辑。

#### Scenario: 统一 patch 入口
- **WHEN** skill 被复制到运行工作目录
- **THEN** 系统通过统一 `patch_skill_md` 完成指令注入
- **AND** 不使用独立 completion-only 注入分支
