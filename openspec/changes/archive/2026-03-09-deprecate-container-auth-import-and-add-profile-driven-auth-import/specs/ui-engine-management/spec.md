## ADDED Requirements

### Requirement: engine auth menu MUST expose profile-driven credential import
管理 UI 的引擎鉴权菜单 MUST 支持文件导入，并由后端 profile 规则动态决定所需文件与写盘路径提示。

#### Scenario: non-opencode engines render import option
- **GIVEN** 引擎为 codex/gemini/iflow
- **WHEN** 用户打开鉴权菜单
- **THEN** UI MUST 在鉴权方式列表中提供导入入口并与原入口使用分隔符分组

#### Scenario: opencode render provider-scoped import option
- **GIVEN** 引擎为 opencode 且 provider 为 oauth provider（openai/google）
- **WHEN** 用户展开 provider 菜单
- **THEN** UI MUST 在 provider 三级菜单提供导入入口
- **AND** provider=google 时 MUST 显示高风险提示
