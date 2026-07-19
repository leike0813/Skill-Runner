## MODIFIED Requirements

### Requirement: 管理界面 MUST 提供独立 Settings 页面

系统 MUST 提供 `/ui/settings` 页面，承载插件状态与更新、运行时设置和高危维护操作。

#### Scenario: 打开 Settings 页面
- **WHEN** 用户访问 `/ui/settings`
- **THEN** 页面在日志设置上方展示 Zotero Bridge CLI 插件区域
- **AND** 继续展示日志设置与 data reset 危险区

## ADDED Requirements

### Requirement: Settings 页面 MUST 支持 Zotero Bridge CLI 两阶段手动更新

Settings 页面 MUST 展示当前实际生效插件的版本和来源，并允许管理员先检查更新、再明确安装已确认更新。

#### Scenario: 查看当前插件状态
- **WHEN** 管理员打开 Settings 页面
- **THEN** 首屏显示当前版本
- **AND** 来源显示为内建或已下载更新

#### Scenario: 检查到可用更新
- **WHEN** 管理员点击检查更新且远端存在新 commit
- **THEN** 页面显示存在可用更新
- **AND** 启用安装更新按钮

#### Scenario: 安装更新
- **WHEN** 管理员点击安装更新
- **THEN** 页面在操作期间禁用更新按钮
- **AND** 安装完成后刷新当前版本、来源和状态
- **AND** 通过可访问的状态区域反馈成功或失败
