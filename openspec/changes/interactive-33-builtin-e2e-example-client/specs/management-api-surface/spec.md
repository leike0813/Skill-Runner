## ADDED Requirements

### Requirement: Skill 管理 MUST 暴露可用于动态表单构建的 schema 内容
系统 MUST 提供 management API 能力，让客户端可读取某个 Skill 的 input/parameter/output schema 内容，以支持动态执行表单和前置校验。

#### Scenario: 读取 Skill schema 集合
- **WHEN** 客户端请求指定 Skill 的 schema 信息
- **THEN** 系统返回该 Skill 的 input/parameter/output schema 内容（若存在）
- **AND** 响应结构可被前端直接用于动态表单渲染与校验

#### Scenario: Skill 不存在
- **WHEN** 客户端请求不存在的 skill_id 的 schema 信息
- **THEN** 系统返回 `404`
- **AND** 不暴露文件系统内部路径细节
