# ui-home-navigation Specification

## Purpose
TBD - created by archiving change ui-auth-shell-and-home-nav-polish. Update Purpose after archive.
## Requirements
### Requirement: UI 首页 MUST 提供清晰且美观的功能入口
系统 MUST 将首页的核心管理入口（Engine 管理、Run 观测）以更易发现的视觉组件呈现，而非仅文本链接。

#### Scenario: 首页加载
- **WHEN** 用户访问 `/ui`
- **THEN** 页面展示卡片化（或等价）入口组件
- **AND** 用户可直达 Engine 管理与 Run 观测页面

### Requirement: 文档 MUST 说明网页鉴权终端依赖与平台差异
系统文档 MUST 包含网页鉴权终端的依赖说明，特别是 Windows 运行所需依赖。

#### Scenario: 用户查看 README/部署文档
- **WHEN** 用户阅读项目 README 或部署相关文档
- **THEN** 文档明确列出该能力的运行依赖（包含 `pywinpty`）
- **AND** 文档说明依赖缺失时的排查路径

