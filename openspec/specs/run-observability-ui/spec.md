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

### Requirement: Run 页面 MUST 支持对话窗口式管理体验
系统 MUST 让内建 Run 页面在统一管理接口下支持对话窗口所需能力：stdout 作为主对话窗口实时更新、底部用户输入框提交 reply、stderr 在独立窗口展示。

#### Scenario: waiting_user 交互
- **WHEN** Run 状态进入 `waiting_user`
- **THEN** 页面展示 pending 信息并激活底部输入框
- **AND** 用户可在同一对话区提交 reply 并恢复执行

#### Scenario: 实时输出观测
- **WHEN** Run 状态为 `running`
- **THEN** 页面消费 SSE 输出事件并实时更新 stdout 主对话窗口
- **AND** 断线后可续传恢复

#### Scenario: stderr 独立展示
- **WHEN** SSE 返回 stderr 增量事件
- **THEN** 页面在独立 stderr 窗口中追加显示错误输出
- **AND** stderr 显示不影响 stdout 主对话窗口的阅读与输入操作

#### Scenario: 用户主动终止
- **WHEN** 用户在 Run 页面触发 cancel
- **THEN** 页面调用 management API 的 cancel 动作
- **AND** 页面状态收敛到 `canceled` 并停止继续交互

