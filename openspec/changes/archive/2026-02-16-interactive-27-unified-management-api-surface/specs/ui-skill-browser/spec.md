## ADDED Requirements

### Requirement: Skill 浏览与管理信息 MUST 通过通用管理 API 暴露
系统 MUST 提供可复用的 Skill 管理接口，以支持内置 UI 与外部前端复用同一数据语义。

#### Scenario: 获取 Skill 列表
- **WHEN** 客户端请求 Skill 列表
- **THEN** 响应包含技能标识、版本、引擎支持、健康状态等稳定字段

#### Scenario: 获取 Skill 详情与结构化内容
- **WHEN** 客户端请求 Skill 详情
- **THEN** 响应包含 schemas/entrypoints/files 等结构化信息
- **AND** 文件路径越界或不存在时返回标准错误码
