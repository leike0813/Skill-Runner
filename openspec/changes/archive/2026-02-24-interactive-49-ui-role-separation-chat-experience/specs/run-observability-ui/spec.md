## MODIFIED Requirements

### Requirement: 系统 MUST 提供 Run 观测 UI 入口
系统 MUST 提供按 request_id 查询 run 观测信息的 UI 页面，并关联 run_id 展示运行实体信息。

#### Scenario: 访问 Run 详情页
- **WHEN** 用户访问 `/ui/runs/{request_id}`
- **THEN** 页面展示该 request 对应 run 的元信息与文件状态
- **AND** 页面提供 run 目录文件树只读浏览能力
- **AND** 页面作为管理审计视图，不提供 reply 输入能力

### Requirement: 管理 Run 详情页 MUST 聚焦审计与排障
管理 Run 详情页 MUST 展示 FCMP 对话、协议审计历史与 raw 输出，用于观测与故障定位。

#### Scenario: 协议审计面板可见
- **WHEN** 管理用户打开 `/ui/runs/{request_id}`
- **THEN** 页面展示 FCMP、RASP、orchestrator 三类审计流面板
- **AND** 面板数据通过管理 protocol history 接口拉取

#### Scenario: waiting_user 不提供内嵌回复
- **WHEN** Run 处于 `waiting_user`
- **THEN** 页面仍可展示 pending 状态事实
- **AND** 页面不渲染回复输入框或提交按钮
