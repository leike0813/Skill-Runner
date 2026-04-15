# web-management-ui Specification

## Purpose
定义基于 Jinja2 SSR 的 Management Web UI 的页面结构、路由和数据绑定约束。
## Requirements
### Requirement: 系统 MUST 提供 `/ui` 管理界面用于技能可视化管理
系统 MUST 暴露 `/ui` 页面，用户可在页面中查看当前已安装技能列表。

#### Scenario: 打开管理界面
- **WHEN** 用户访问 `/ui`
- **THEN** 系统返回可用页面
- **AND** 页面包含技能列表区域与技能包上传区域
- **AND** data reset 危险区不再直接出现在首页

### Requirement: 管理界面 MUST 展示技能用途信息
管理界面技能列表 MUST 至少展示每个技能的 `id`、`name`、`description`、`version` 与 `engines`。

#### Scenario: 查看技能用途
- **WHEN** 管理界面加载技能列表
- **THEN** 用户可看到每个技能的用途描述（`description`）

### Requirement: 管理界面 MUST 支持交互式安装 Skill 包
系统 MUST 提供网页上传 Skill 包的入口，并触发异步安装流程。

#### Scenario: 上传并发起安装
- **WHEN** 用户在页面选择 zip 包并提交安装
- **THEN** 系统创建安装请求并返回 request_id
- **AND** 页面展示当前安装状态

### Requirement: 管理界面 MUST 支持安装状态轮询与结果反馈
系统 MUST 支持对安装 request_id 的状态轮询，并在终态展示结果。

#### Scenario: 安装成功后刷新列表
- **WHEN** 某次安装状态进入 `succeeded`
- **THEN** 页面自动刷新技能列表
- **AND** 新安装技能在列表中高亮显示

#### Scenario: 安装失败时展示错误
- **WHEN** 某次安装状态进入 `failed`
- **THEN** 页面展示后端返回的错误原因

### Requirement: 管理界面 MUST 提供独立 Settings 页面
系统 MUST 提供 `/ui/settings` 页面，承载运行时设置与高危维护操作。

#### Scenario: 打开 Settings 页面
- **WHEN** 用户访问 `/ui/settings`
- **THEN** 页面展示日志设置区域与 data reset 危险区

### Requirement: 管理界面 MUST 让 data reset 选项反映真实系统能力
系统 MUST 依据当前系统能力显示或隐藏可选清理项，避免暴露未启用能力的伪选项。

#### Scenario: engine auth session 日志持久化关闭
- **WHEN** `ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED` 为关闭状态
- **THEN** `/ui/settings` 页面完全隐藏 engine auth session 清理选项

### Requirement: 管理界面 MUST 支持最小运行时日志设置管理
系统 MUST 在 Settings 页面提供最小可写日志设置，并展示不可在页面修改的只读运行时输入。

#### Scenario: 查看 Settings 页面日志设置
- **WHEN** 用户访问 `/ui/settings`
- **THEN** 页面展示可写日志设置 `level`、`format`、`retention_days`、`dir_max_bytes`
- **AND** 页面展示只读日志输入 `dir`、`file_basename`、`rotation_when`、`rotation_interval`

### Requirement: Engine 管理页面 MUST 服务端直出首屏表格
系统 MUST 在 `/ui/engines` 首屏直接返回 engine 表格，而不是依赖首次 HTMX 拉取来补全内容。

#### Scenario: 打开 engine 管理页
- **WHEN** 用户访问 `/ui/engines`
- **THEN** 页面首屏直接包含 engine 表格
- **AND** 不依赖 `hx-get` 首次加载表格
- **AND** 不展示“正在检测 Engine 版本与状态，请稍候...”之类延迟探测文案

#### Scenario: 模型管理页统一为单一 model 展示语义
- **WHEN** 用户访问 `/ui/engines/{engine}/models`
- **THEN** 模型列表不再显示 `display_name` 列
- **AND** `opencode` 继续在 `model` 列显示当前 `model` 值
- **AND** 其他引擎在 `model` 列显示原 `display_name` 内容

#### Scenario: 非 opencode 模型快照表单统一为 model 输入
- **WHEN** 用户在非 `opencode` 模型管理页新增快照行
- **THEN** 表单不再单独提供 `display_name` 输入
- **AND** 页面以单一 `model` 输入承载原显示名语义

#### Scenario: opencode 手动刷新通过局部更新返回
- **WHEN** 用户在 `opencode` 模型管理页点击手动刷新
- **THEN** 页面 MUST 通过 HTMX 局部替换更新模型管理 panel
- **AND** 不得退回整页重定向刷新

### Requirement: Engine 表格 MUST 仅展示缓存化版本
系统 MUST 让 engine 管理表格只展示后台缓存的版本信息，不在页面访问时触发 CLI 版本探测。

#### Scenario: 查看 engine 表格版本列
- **WHEN** 用户查看 engine 管理表格
- **THEN** `CLI Version` 列来自持久化缓存
- **AND** 页面加载时不会触发 CLI 版本探测

### Requirement: Engine 表格 MUST 移除 auth 与 sandbox 列
系统 MUST 从 engine 管理表格中删除 auth 和 sandbox 摘要列。

#### Scenario: 查看 engine 表格列定义
- **WHEN** 用户查看 `/ui/engines`
- **THEN** 表格不包含 `Auth Ready`
- **AND** 表格不包含 `Sandbox`

### Requirement: 旧 UI 数据接口 MUST 进入弃用生命周期
系统 MUST 为历史 UI 专用数据接口提供可执行的弃用路径，并给出替代 management API。

#### Scenario: Deprecation 标记
- **WHEN** 客户端调用旧 UI 数据接口
- **THEN** 响应包含弃用提示（文档与/或响应元信息）
- **AND** 明确替代 management API 路径

#### Scenario: 内建 UI 脱离旧接口
- **WHEN** 弃用阶段完成
- **THEN** 内建 Web 客户端不再调用旧 UI 数据接口
- **AND** 核心管理页面功能保持可用

### Requirement: Run 观测详情页 MUST 使用稳定分区布局
系统 MUST 在内建管理界面的 Run 详情页使用稳定分区布局，确保文件浏览区、主对话区、错误区在长内容场景下仍可持续操作。

#### Scenario: 分区布局可持续操作
- **WHEN** 用户访问 `/ui/runs/{request_id}`
- **THEN** 页面同时提供文件浏览区、stdout 主对话区、stderr 独立区
- **AND** 用户无需切换页面即可完成查看输出与提交 reply

#### Scenario: 长内容不拉伸整页
- **WHEN** 文件树、文件预览或日志内容持续增长
- **THEN** 对应分区在内部容器滚动
- **AND** 页面主结构保持稳定，不出现无限增高导致的交互退化

### Requirement: Management run detail MUST render backend-projected chat text
The management run-detail page MUST treat canonical chat as a backend-derived display surface and MUST NOT perform its own structured-output dispatch.

#### Scenario: final structured output appears in management chat
- **WHEN** `/chat` supplies assistant final text rendered as markdown
- **THEN** the management run-detail page MUST render that markdown in chat
- **AND** it MUST NOT re-parse raw structured JSON to decide how to display the message

#### Scenario: pending structured output appears in management chat
- **WHEN** `/chat` supplies pending display text
- **THEN** the management run-detail page MUST render the projected text directly
- **AND** it MUST NOT add a second final summary card for the same content

### Requirement: Management run detail chat MUST use the shared markdown renderer
The management run-detail page MUST render canonical chat with the same shared markdown renderer and scoped markdown styles used by the built-in E2E observe client.

#### Scenario: markdown chat content appears in run detail
- **WHEN** the management run-detail page renders chat text from `/chat` or `/chat/history`
- **THEN** it MUST use the shared chat markdown assets
- **AND** it MUST render formulas, code blocks, lists, tables, and quotes with the same markdown capabilities as the E2E observe page
- **AND** it MUST NOT rely on browser default paragraph margins for chat spacing

### Requirement: Management run detail MUST expose raw chat event inspection
The management run-detail page MUST allow operators to inspect the raw `chat-replay` event envelope behind chat items without leaving the canonical chat view.

#### Scenario: operator inspects a chat bubble
- **WHEN** the operator clicks a normal chat bubble
- **THEN** the page MUST open a right-side inspector drawer
- **AND** the drawer MUST show the corresponding raw `chat-replay` event envelope
- **AND** the drawer MAY expose a `raw_ref` preview jump when available

#### Scenario: operator inspects a thinking or process child item
- **WHEN** the operator expands a thinking/process group and selects a child item inspector trigger
- **THEN** the page MUST open the same inspector drawer for that child item's `chat-replay` event envelope
- **AND** the expand/collapse interaction MUST remain intact

### Requirement: Management run detail MUST use one shared event inspector drawer
The management run-detail page MUST use a single right-side event inspector drawer for chat, protocol streams, and timeline event inspection.

#### Scenario: operator inspects a protocol stream row
- **WHEN** the operator clicks a FCMP, RASP, or Orchestrator row while raw mode is disabled
- **THEN** the page MUST open the shared right-side event inspector drawer
- **AND** it MUST show the corresponding audit row envelope
- **AND** it MUST NOT expand a local inline detail block inside the protocol pane

#### Scenario: operator inspects a timeline event
- **WHEN** the operator clicks a timeline bubble
- **THEN** the page MUST open the same shared right-side event inspector drawer
- **AND** it MUST show the corresponding timeline event payload
- **AND** it MUST NOT expand a local inline detail block inside the timeline pane

### Requirement: Management run detail chat MUST expose clickable affordance
Clickable chat items in the management run-detail page MUST provide visible hover or focus feedback.

#### Scenario: operator hovers a clickable chat message
- **WHEN** the operator hovers a clickable chat entry
- **THEN** the entry MUST show a visible hover affordance aligned with the protocol-pane interaction style
- **AND** the existing keyboard focus indication MUST remain available

