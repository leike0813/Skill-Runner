# web-client-management-api-adapter Specification

## Purpose
TBD - created by archiving change interactive-28-web-client-management-api-migration. Update Purpose after archive.
## Requirements
### Requirement: 内建 Web 客户端 MUST 优先消费 management API
系统 MUST 确保内建 Web 客户端在 Skill/Engine/Run 三域的数据读取与操作优先通过 `/v1/management/*` 完成。

#### Scenario: Skill 页面数据来源
- **WHEN** 用户访问内建 Skill 管理页面
- **THEN** 页面数据由 management API 提供
- **AND** 不依赖旧 UI 专用数据接口

#### Scenario: Engine 页面数据来源
- **WHEN** 用户访问内建 Engine 管理页面
- **THEN** 页面数据由 management API 提供
- **AND** 字段语义与外部前端一致

#### Scenario: Run 页面数据来源
- **WHEN** 用户访问内建 Run 管理页面
- **THEN** 状态、文件浏览、交互动作、实时输出能力均由 management API 提供统一语义
- **AND** 终止动作（cancel）由 management API 提供

