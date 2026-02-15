## ADDED Requirements

### Requirement: Installed skill package MUST strip Git metadata
系统 MUST 在 skill package 安装流程中移除技能包内的 Git 元数据，避免与父仓库产生冲突。

#### Scenario: Fresh install strips `.git` directory
- **GIVEN** 上传的 skill package 已通过结构与版本校验
- **AND** 包内容包含 `.git/` 目录
- **WHEN** 系统执行安装
- **THEN** 最终 `skills/<skill_id>/` 目录中不包含 `.git/`
- **AND** 安装仍按正常流程完成

#### Scenario: Update install strips `.git` file
- **GIVEN** 已存在可更新的 `skills/<skill_id>/`
- **AND** 新上传包包含 `.git` 普通文件
- **WHEN** 系统执行更新安装
- **THEN** 更新后的 `skills/<skill_id>/` 中不包含 `.git` 文件
- **AND** 旧版本归档流程保持不变

#### Scenario: Non-git hidden files are preserved
- **GIVEN** 上传包中包含 `.gitignore`、`.github/` 等非 `.git` 名称文件或目录
- **WHEN** 系统执行安装或更新
- **THEN** 系统仅清理名称精确为 `.git` 的文件或目录
- **AND** 其他隐藏文件不因该策略被删除
