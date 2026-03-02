# run-observability-ui Specification

## Purpose
定义 Run 观测 UI 的入口、文件只读预览和实时日志展示约束。

## MODIFIED Requirements

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
