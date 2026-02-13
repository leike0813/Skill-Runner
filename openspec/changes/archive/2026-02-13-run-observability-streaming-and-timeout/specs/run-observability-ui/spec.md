## ADDED Requirements

### Requirement: 系统 MUST 提供 Run 观测 UI 入口
系统 MUST 提供按 request_id 查询 run 观测信息的 UI 页面，并关联 run_id 展示运行实体信息。

#### Scenario: 访问 Run 列表页
- **WHEN** 用户访问 `/ui/runs`
- **THEN** 页面展示 request_id 对应的 run 列表
- **AND** 每条记录包含 run_id、skill、engine、status、updated_at

#### Scenario: 访问 Run 详情页
- **WHEN** 用户访问 `/ui/runs/{request_id}`
- **THEN** 页面展示该 request 对应 run 的元信息与文件状态
- **AND** 页面提供 run 目录文件树只读浏览能力

### Requirement: 系统 MUST 支持 Run 文件只读预览
系统 MUST 允许用户在 UI 中预览 run 目录文件内容，且不得提供修改入口。

#### Scenario: 预览文本文件
- **WHEN** 用户请求 `/ui/runs/{request_id}/view?path=<relative_path>`
- **THEN** 系统返回对应文件预览内容
- **AND** 仅允许 run 目录内的安全路径

#### Scenario: 非法路径被拒绝
- **WHEN** 用户请求路径越界或文件不存在
- **THEN** 系统返回错误响应（400 或 404）

### Requirement: 系统 MUST 提供运行中日志动态刷新
系统 MUST 提供 run 日志 tail 接口，并在运行态支持 UI 自动刷新。

#### Scenario: 运行态轮询
- **WHEN** run 状态为 `queued` 或 `running`
- **THEN** `/ui/runs/{request_id}/logs/tail` 响应标记 `poll=true`
- **AND** UI 持续轮询刷新 stdout/stderr tail
