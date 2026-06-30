## MODIFIED Requirements

### Requirement: Harness MUST 在运行前注入项目与夹具技能包
系统 MUST 在每次 attempt 启动前将技能包注入到 run 目录的引擎技能根，来源同时覆盖项目根 `skills/` 与 `tests/fixtures/skills/`，目标路径 MUST 来自 adapter profile workspace metadata。

#### Scenario: 同时注入项目技能与 fixtures 技能
- **WHEN** harness 启动一次引擎执行
- **THEN** 从 `<project_root>/skills/` 与 `<project_root>/tests/fixtures/skills/` 扫描技能目录并注入
- **AND** 注入目标路径为 `<run_dir>/<profile.attempt_workspace.workspace_subdir>/<profile.attempt_workspace.skills_subdir>/`

#### Scenario: 注入摘要可审计追踪
- **WHEN** harness 完成一次 attempt 并写入 meta 审计文件
- **THEN** meta 中包含 skill 注入摘要（source_roots、target_root、skill_count、skills）
- **AND** 注入缺失或空来源时仍输出结构化摘要（skill_count=0）
