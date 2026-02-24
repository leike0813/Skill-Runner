# run-observability-ui Specification

## Purpose
TBD - created by archiving change run-observability-streaming-and-timeout. Update Purpose after archive.
## Requirements
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
系统 MUST 允许用户在 UI 中预览 run 目录文件内容，且不得提供修改入口；文件树与预览区在页面中 MUST 使用固定最大高度并支持内部滚动，以避免详情页被长内容无限拉伸。

#### Scenario: 预览文本文件
- **WHEN** 用户请求 `/ui/runs/{request_id}/view?path=<relative_path>`
- **THEN** 系统返回对应文件预览内容
- **AND** 仅允许 run 目录内的安全路径

#### Scenario: 非法路径被拒绝
- **WHEN** 用户请求路径越界或文件不存在
- **THEN** 系统返回错误响应（400 或 404）

#### Scenario: 文件树与预览长内容滚动
- **WHEN** 文件树项数量或预览文本长度超过详情页区块最大高度
- **THEN** 文件树区与预览区在各自容器内滚动显示
- **AND** 页面整体高度保持稳定，不因长内容持续增长

### Requirement: 系统 MUST 提供运行中日志动态刷新
系统 MUST 提供 run 日志 tail 接口，并在运行态支持 UI 自动刷新。

#### Scenario: 运行态轮询
- **WHEN** run 状态为 `queued` 或 `running`
- **THEN** `/ui/runs/{request_id}/logs/tail` 响应标记 `poll=true`
- **AND** UI 持续轮询刷新 stdout/stderr tail

### Requirement: Run 可观测能力 MUST 优先通过通用管理 API 暴露
系统 MUST 提供可被任意前端复用的 Run 可观测接口，UI 页面仅作为消费方。

#### Scenario: 通用 API 覆盖 Run 观测核心字段
- **WHEN** 客户端查询 Run 观测状态
- **THEN** 可通过通用管理 API 获取状态、交互态、日志流消费信息
- **AND** 不要求客户端依赖 `/ui/*` HTML 接口

#### Scenario: UI 页面复用通用 API 语义
- **WHEN** 内置 UI 展示 Run 详情与日志
- **THEN** 展示字段语义与通用管理 API 保持一致
- **AND** 不引入仅 UI 可见的私有状态定义

### Requirement: Run 页面 MUST 聚焦审计与排障
Run 管理页面 MUST 作为观测/审计工具，不承担终端用户交互回复职责。

#### Scenario: 管理页不提供 reply 输入
- **WHEN** 用户访问 `/ui/runs/{request_id}`
- **THEN** 页面不渲染 pending reply 输入框和提交按钮
- **AND** 页面保留 cancel 等运维动作

#### Scenario: 审计视图完整
- **WHEN** 用户在 run 详情页审计执行过程
- **THEN** 页面展示 FCMP 对话流
- **AND** 展示 FCMP/RASP/orchestrator 审计事件面板
- **AND** 支持 raw stderr 与 raw_ref 片段回跳预览

### Requirement: 管理页审计面板 MUST 支持按 attempt 翻页
系统 MUST 提供按轮次切换审计内容的能力，避免多轮运行日志互相覆盖。

#### Scenario: 审计面板按轮次切换
- **WHEN** 用户在 run 详情页点击左右箭头切换 attempt
- **THEN** FCMP/RASP/orchestrator/raw stderr 同步切换到目标轮次
- **AND** 页内显示当前轮次与可用轮次范围
- **AND** 轮次切换控件位于对话回放区与流观测区之间
- **AND** 对话区序号优先显示 `meta.local_seq`

#### Scenario: 重进页面可见历史
- **WHEN** 用户重新打开 `/ui/runs/{request_id}`
- **THEN** 页面先加载历史审计与对话
- **AND** 再接入实时 SSE 增量事件

#### Scenario: 对话回放不重复展示问询正文
- **WHEN** FCMP 同时出现 `assistant.message.final` 与 `user.input.required`
- **THEN** 对话区优先展示 assistant 正文
- **AND** `user.input.required` 仅作为控制语义，不重复生成同文气泡

#### Scenario: 用户回复可回放
- **WHEN** FCMP `interaction.reply.accepted` 包含 `response_preview`
- **THEN** 管理页对话区展示 User 气泡
- **AND** 重进页面后可按历史顺序回放

#### Scenario: raw_ref 与 stderr 位置优化
- **WHEN** 用户在 run 详情页审计协议与 raw 日志
- **THEN** `raw_ref` 预览窗口位于对话区旁
- **AND** `Raw stderr` 位于下方审计操作区，便于联动查看
