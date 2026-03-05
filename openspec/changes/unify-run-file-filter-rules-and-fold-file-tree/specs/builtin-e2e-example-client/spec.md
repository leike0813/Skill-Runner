## ADDED Requirements

### Requirement: 示例客户端文件树 MUST 默认目录折叠

示例客户端 Observation 页文件树 MUST 与管理 UI 一致，默认目录折叠并支持点击展开/收起。

#### Scenario: observation file tree starts collapsed
- **WHEN** 用户打开 `/runs/{request_id}`
- **THEN** 文件树目录默认折叠
- **AND** 用户展开目录后才显示子节点

### Requirement: 示例客户端 run explorer data MUST respect backend denylist filtering

示例客户端显示的 run 文件树与预览 MUST 基于后端过滤后的结果，不得在前端重新放宽可见集合。

#### Scenario: ignored paths never rendered in client tree
- **WHEN** 后端返回的 run 文件树已应用 debug 黑名单过滤
- **THEN** 客户端 MUST 仅渲染返回结果
- **AND** 命中黑名单的目录（例如 `node_modules`）不得出现在页面
