## ADDED Requirements

### Requirement: 管理 UI Run Detail MUST 提供 Run Scope 时序图
系统 MUST 在管理 UI Run Detail 页面底部提供默认折叠的 Run Timeline 视图，并以固定五泳道展示 run 级时序事件。

#### Scenario: 默认折叠并可展开查看
- **WHEN** 用户打开 Run Detail 页面
- **THEN** Run Timeline 区域默认折叠
- **AND** 用户可手动展开查看时序图内容

#### Scenario: 五泳道固定顺序展示
- **WHEN** 时间线面板展开
- **THEN** 系统按 Orchestrator、Parser/RASP、Protocol/FCMP、Chat history、Client 顺序展示泳道

#### Scenario: 气泡展开详情与 raw_ref 回跳
- **WHEN** 用户点击时间线气泡
- **THEN** 系统展开该事件详情并展示结构化信息
- **AND** 若事件包含 raw_ref，用户可触发回跳预览
