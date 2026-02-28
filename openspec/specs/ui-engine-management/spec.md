## Purpose
定义 Web UI 中 Engine 管理与 Model Manifest 管理的行为，确保用户可查看状态、执行升级并可视化查看/补录模型快照。
## Requirements
### Requirement: UI MUST 提供 Engine 状态总览页面
系统 MUST 在 UI 提供 Engine 管理页面，显示引擎可用性与版本号。

#### Scenario: 打开 Engine 管理页
- **WHEN** 用户访问 `/ui/engines`
- **THEN** 页面显示 `codex/gemini/iflow/opencode` 状态
- **AND** 显示每个引擎的版本号（若可检测）

### Requirement: UI MUST 支持按引擎升级与全部升级
系统 MUST 在 UI 提供“单引擎升级”与“全部升级”交互入口。

#### Scenario: 点击单引擎升级
- **WHEN** 用户点击某引擎的升级按钮
- **THEN** UI 创建单引擎升级任务并展示任务状态

#### Scenario: 点击全部升级
- **WHEN** 用户点击“升级全部”
- **THEN** UI 创建全引擎升级任务并展示任务状态

### Requirement: UI MUST 展示 per-engine stdout/stderr
系统 MUST 在升级状态视图中展示每个引擎的 stdout/stderr。

#### Scenario: 升级任务终态
- **WHEN** 升级任务进入 `succeeded` 或 `failed`
- **THEN** UI 显示每个引擎的执行结果
- **AND** 显示 per-engine stdout/stderr

### Requirement: Engine 升级管理 MUST 受 Basic Auth 保护
当 UI Basic Auth 启用时，Engine 管理页面与升级接口 MUST 需要认证。

#### Scenario: 未认证访问 Engine 管理页
- **WHEN** 未认证访问 `/ui/engines`
- **THEN** 系统返回 `401`

### Requirement: UI MUST 提供 Engine Model Manifest 管理页面
系统 MUST 提供按 Engine 的模型清单管理页面，支持查看当前 manifest 解析结果和模型列表。

#### Scenario: 进入模型管理页
- **WHEN** 用户在 `/ui/engines` 点击某 Engine 的“模型管理”
- **THEN** 跳转到 `/ui/engines/{engine}/models`
- **AND** 页面展示 `cli_version_detected`、resolved snapshot 与模型列表

### Requirement: UI MUST 支持新增当前版本模型快照
系统 MUST 在模型管理页提供“新增当前版本快照”表单，字段包含 `id/display_name/deprecated/notes/supported_effort`。

#### Scenario: 新增成功后立即刷新
- **WHEN** 用户提交合法模型列表并新增成功
- **THEN** 页面立即刷新并显示新的 manifest 解析结果与模型数据

#### Scenario: 目标版本快照已存在
- **WHEN** 用户尝试新增已存在版本快照
- **THEN** 页面展示拒绝错误信息
- **AND** 现有模型列表不被覆盖

### Requirement: Model Manifest 管理 MUST 受 Basic Auth 保护
当 UI Basic Auth 启用时，模型管理页面与相关 API MUST 需要认证。

#### Scenario: 未认证访问模型管理页
- **WHEN** 未认证访问 `/ui/engines/{engine}/models`
- **THEN** 系统返回 `401`

### Requirement: Engine 管理 UI MUST 基于通用管理 API 字段渲染
系统 MUST 让 Engine 管理相关核心信息可通过通用管理 API 获取，UI 不应依赖私有拼装字段。

#### Scenario: 获取 Engine 概览信息
- **WHEN** 客户端请求 Engine 管理概览
- **THEN** 响应包含版本、认证状态、沙箱状态等稳定字段

#### Scenario: 获取 Engine 详情信息
- **WHEN** 客户端请求 Engine 管理详情
- **THEN** 响应包含模型列表与升级状态信息
- **AND** 字段可被非内置 UI 前端直接消费

### Requirement: Engine 管理页面字段 MUST 对齐 management API
系统 MUST 保证内建 Engine 管理页面使用 management API 稳定字段，不依赖 UI 私有拼装。

#### Scenario: 引擎概览渲染
- **WHEN** 页面渲染引擎概览
- **THEN** 版本、认证状态、沙箱状态来源于 management API 标准字段

#### Scenario: 升级状态渲染
- **WHEN** 页面渲染升级状态与结果
- **THEN** 数据来源与外部前端可消费的管理接口语义一致

### Requirement: 执行表单模型选择 MUST 支持 provider/model 双下拉
系统 MUST 在执行表单中提供统一的 provider + model 选择交互，兼容现有单 `model` 字段提交。

#### Scenario: 非 opencode 引擎使用固定 provider
- **WHEN** 用户在执行表单选择 `codex`、`gemini` 或 `iflow`
- **THEN** provider 下拉仅显示一个固定值（`openai/google/iflowcn`）
- **AND** 提交给后端的 `model` 语义与现有行为一致

#### Scenario: opencode 引擎按 provider 过滤模型
- **WHEN** 用户在执行表单选择 `opencode`
- **THEN** provider 选项来自后端模型返回
- **AND** model 下拉按所选 provider 过滤
- **AND** 最终提交 `model` 为 `provider/model` 形式

### Requirement: 管理 UI 鉴权行为 MUST 对重构透明
系统 MUST 保持 `/ui/engines` 鉴权交互与现有 transport 接口契约兼容，不因内部目录重构改变用户可见行为。

#### Scenario: 发起与轮询鉴权
- **WHEN** 管理 UI 调用现有鉴权接口（oauth_proxy/cli_delegate）
- **THEN** 启动、轮询、输入、取消行为保持兼容
- **AND** 无需修改客户端请求路径或字段

### Requirement: 能力矩阵来源 MUST 由后端统一注入
系统 MUST 在重构后保持 `auth_ui_capabilities` 注入语义稳定，避免前端硬编码回归。

#### Scenario: 页面渲染能力矩阵
- **WHEN** UI 渲染 `/ui/engines`
- **THEN** 能力矩阵仍来自后端上下文注入
- **AND** 能力矩阵与后端 driver capability 保持一致

### Requirement: Engine 管理页 MUST 支持四引擎统一鉴权入口
系统 MUST 在 `/ui/engines` 为 `codex/gemini/iflow/opencode` 提供统一鉴权入口，并通过会话轮询展示状态。

#### Scenario: 任意引擎启动鉴权会话
- **WHEN** 用户从引擎入口菜单选择鉴权方式
- **THEN** UI 调用鉴权 start 接口并展示当前会话状态
- **AND** 状态轮询统一使用会话快照

#### Scenario: 会话取消
- **WHEN** 用户点击取消按钮
- **THEN** UI 调用 cancel 接口
- **AND** 会话进入 `canceled`

### Requirement: 鉴权会话与内嵌 TUI MUST 全局互斥
系统 MUST 防止鉴权会话与内嵌 TUI 会话并发进行。

#### Scenario: TUI 活跃时启动鉴权
- **WHEN** 内嵌 TUI 会话处于活跃状态
- **AND** 用户尝试启动任意引擎鉴权会话
- **THEN** 系统返回 `409`
- **AND** UI 展示冲突提示

#### Scenario: 鉴权活跃时启动 TUI
- **WHEN** 任意鉴权会话处于活跃状态
- **AND** 用户尝试启动内嵌 TUI
- **THEN** 系统返回 `409`
- **AND** UI 展示冲突提示

### Requirement: 管理 UI MUST 以新 auth_method 语义驱动菜单
系统 MUST 使用 `callback|auth_code_or_url|api_key` 作为 UI 鉴权方式菜单值，不再使用历史方式值。

#### Scenario: 菜单项渲染
- **WHEN** 用户打开任一引擎鉴权菜单
- **THEN** 菜单仅展示新语义方式值
- **AND** 旧值不会出现在前端菜单与请求体中

### Requirement: UI start 请求 MUST 透传 auth_method
系统 MUST 在鉴权启动请求中携带 `auth_method`，而非仅依赖历史 `method`。

#### Scenario: 点击分层菜单项
- **WHEN** 用户从引擎入口分层菜单选择任一鉴权方式
- **THEN** UI 请求体包含 `transport + auth_method`
- **AND** opencode/openai 请求体携带 `provider_id=openai`

### Requirement: 输入区展示 MUST 与 auth_method 匹配
系统 MUST 根据 `engine + transport + auth_method + input_kind` 控制输入区和提示文案。

#### Scenario: callback 模式
- **WHEN** 会话为 `callback` 且需要手工回填
- **THEN** 显示 redirect URL/code 粘贴提示与提交入口

#### Scenario: auth_code_or_url 模式
- **WHEN** 会话为 `auth_code_or_url` 且不需要用户向后端回填
- **THEN** 不显示输入框
- **AND** 保留 `verification_url + user_code` 展示

### Requirement: 提交后隐藏行为 MUST 继续生效
系统 MUST 保持“输入提交后隐藏输入区与鉴权链接”的既有行为，避免重复误操作。

#### Scenario: 提交成功接受
- **WHEN** `/input` 返回 `accepted=true`
- **THEN** 输入区与链接区域隐藏
- **AND** 状态切换为等待结果

### Requirement: Engine 管理页 MUST 提供 OpenCode Google OAuth 代理独立入口
系统 MUST 在 `/ui/engines` 提供可触发 `opencode+google+oauth_proxy+callback` 的入口。

#### Scenario: 点击按钮启动会话
- **WHEN** 用户点击 OpenCode Google OAuth 代理按钮
- **THEN** UI 调用 `/ui/engines/auth/oauth-proxy/sessions`
- **AND** 请求体包含：
  - `engine=opencode`
  - `transport=oauth_proxy`
  - `provider_id=google`
  - `auth_method=callback`

### Requirement: UI MUST 支持自动回调与手工输入双模式协同
系统 MUST 在同一会话中同时支持自动回调与手工输入兜底，不要求用户区分链路。

#### Scenario: 自动回调成功
- **WHEN** 本地 listener 已接收回调并完成 exchange
- **THEN** UI 轮询状态进入 `succeeded`

#### Scenario: 自动回调不可达时手工兜底
- **WHEN** 用户将回调 URL 或 code 粘贴到输入框并提交
- **THEN** UI 调用 `/ui/engines/auth/oauth-proxy/sessions/{id}/input`
- **AND** 成功后会话收口到终态

### Requirement: OpenCode Google 的 oauth_proxy 与 cli_delegate 入口 MUST 并行可用
系统 MUST 同时保留 OpenCode Google 的 `oauth_proxy` 与 `cli_delegate` 入口能力，由用户按全局 transport 选择。

#### Scenario: transport 切换后入口行为一致
- **WHEN** 用户切换全局 transport 并发起 OpenCode Google 鉴权
- **THEN** 菜单能力与后端 capability 矩阵一致
- **AND** 不因 transport 切换导致入口丢失

### Requirement: Engine 管理页 MUST 使用 transport 分组鉴权接口
系统 MUST 让 Engine 管理页调用 transport 分组接口，而非旧的通用会话接口。

#### Scenario: 发起 oauth_proxy 会话
- **WHEN** 用户点击 OAuth 代理入口
- **THEN** 前端调用 `/ui/engines/auth/oauth-proxy/sessions`

#### Scenario: 发起 cli_delegate 会话
- **WHEN** 用户点击 CLI 委托入口
- **THEN** 前端调用 `/ui/engines/auth/cli-delegate/sessions`

### Requirement: UI MUST 正确展示 transport 专属状态机语义
系统 MUST 根据 transport 展示状态，不得混用状态机含义。

#### Scenario: oauth_proxy 状态展示
- **WHEN** 当前会话 `transport=oauth_proxy`
- **THEN** 页面不得显示 `waiting_orchestrator` 语义

#### Scenario: cli_delegate 状态展示
- **WHEN** 当前会话 `transport=cli_delegate`
- **THEN** 页面可显示 `waiting_orchestrator`，表示后台自动编排阶段

### Requirement: UI MUST 消费标准化会话快照与日志根路径
系统 MUST 让 UI 基于标准化快照渲染，并可读取 `log_root` 用于诊断跳转。

#### Scenario: 拉取会话快照
- **WHEN** 页面轮询鉴权会话状态
- **THEN** 返回字段包含 `transport_state_machine`、`orchestrator`、`log_root`
- **AND** UI 不再依赖解析 transport 特有原始日志文本

### Requirement: Engine 管理页 MUST 使用“单入口 + 分层菜单”鉴权交互
系统 MUST 在引擎表格中为每个引擎仅提供一个鉴权入口按钮，并通过分层菜单选择鉴权方式。

#### Scenario: 非 OpenCode 引擎菜单
- **WHEN** 用户点击 `连接 Codex/Gemini/iFlow`
- **THEN** 页面展示当前全局 transport 下该引擎可用 `auth_method` 列表

#### Scenario: OpenCode 引擎菜单
- **WHEN** 用户点击 `连接 OpenCode`
- **THEN** 页面先展示 provider 列表
- **AND** 选择 provider 后再展示该 provider 的鉴权方式列表

### Requirement: 鉴权状态窗口 MUST 保留状态展示并简化操作按钮
系统 MUST 保留 Engine Auth 状态窗口，但除取消按钮外不再提供启动类按钮。

#### Scenario: 状态窗口按钮集合
- **WHEN** 用户查看 Engine Auth 状态窗口
- **THEN** 窗口仅包含取消按钮
- **AND** 启动鉴权入口只存在于引擎表格

### Requirement: 全局 transport 选择器 MUST 受会话锁控制
系统 MUST 在存在活动 auth 会话或活动 TUI 会话时禁用全局 transport 下拉。

#### Scenario: 鉴权进行中锁定 transport
- **WHEN** 存在活动 auth 会话
- **THEN** transport 下拉禁用
- **AND** 引擎鉴权入口按钮禁用

### Requirement: user_code 复制能力 MUST 在指定场景可用
系统 MUST 在 `codex` 与 `opencode+openai` 的 `auth_code_or_url` 场景显示 user_code 复制按钮。

#### Scenario: 显示复制按钮
- **WHEN** 会话包含 `user_code`
- **AND** `auth_method=auth_code_or_url`
- **AND** `(engine=codex) OR (engine=opencode AND provider_id=openai)`
- **THEN** 页面显示复制按钮并支持复制 user_code
