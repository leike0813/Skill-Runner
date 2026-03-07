## ADDED Requirements

### Requirement: 管理端 System Console MUST 提供系统日志浏览能力
管理 UI MUST 在 `/ui/settings`（文案语义为 System Console）提供日志浏览模块，支持系统日志与 bootstrap 日志的查询与分页展示，并与现有日志设置、数据重置模块并存。

#### Scenario: system console shows log explorer controls
- **WHEN** 用户打开 `/ui/settings`
- **THEN** 页面显示 System Console 标题
- **AND** 显示 Log Explorer 的 source、关键词、级别、时间范围与 Load more 控件
- **AND** 不影响原有 logging settings 与 data reset 控件
