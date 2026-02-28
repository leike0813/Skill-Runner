# engine-auth-observability Specification

## Purpose
TBD - created by archiving change engine-auth-observability-and-failfast. Update Purpose after archive.
## Requirements
### Requirement: 系统 MUST 提供统一 Engine 鉴权状态接口
系统 MUST 提供统一接口返回各 Engine 的鉴权可观测状态，且输出结构可被 UI 与脚本复用。

#### Scenario: 查询鉴权状态成功
- **WHEN** 客户端请求 `GET /v1/engines/auth-status`
- **THEN** 返回每个 engine 的 `managed_present`、`effective_cli_path`、`effective_path_source`
- **AND** 返回白名单凭证文件存在性明细

### Requirement: 系统 MUST 区分 managed 与 global CLI 路径来源
系统 MUST 明确标识当前实际可执行路径来源，避免用户误把全局 CLI 当作 managed CLI。

#### Scenario: managed 缺失但 global 可用
- **WHEN** managed prefix 下不存在某 engine 可执行文件，但 PATH 中存在全局可执行
- **THEN** 状态中 `effective_path_source` 标记为 `global`
- **AND** 提供诊断提示建议安装到 managed prefix

### Requirement: 系统 MUST 提供本地与容器一致的鉴权诊断脚本
系统 MUST 提供脚本化方式输出当前运行时真实鉴权状态。

#### Scenario: 本地运行诊断脚本
- **WHEN** 用户执行鉴权诊断脚本
- **THEN** 脚本输出服务当前 runtime 下各 engine 的路径来源与凭证状态

### Requirement: 系统 MUST 保证 iFlow 在 managed 环境具备最小可用配置基线
系统 MUST 在 managed Agent Home 中确保 iFlow settings 包含可用认证类型与 API 端点，避免因配置缺失导致鉴权状态误判。

#### Scenario: iFlow settings 缺失时初始化基线
- **WHEN** managed `~/.iflow/settings.json` 不存在
- **THEN** 系统写入默认基线配置
- **AND** 至少包含 `selectedAuthType=oauth-iflow` 与 `baseUrl=https://apis.iflow.cn/v1`

#### Scenario: iFlow legacy settings 自动迁移
- **WHEN** managed `~/.iflow/settings.json` 存在但 `selectedAuthType=iflow` 或 `baseUrl` 缺失/非法
- **THEN** 系统自动迁移到默认基线值
- **AND** 不影响白名单凭证文件导入策略（仅导入鉴权文件，不导入外部 settings）

### Requirement: Transport orchestrator MUST 与 engine-specific 逻辑解耦
系统 MUST 保证 transport orchestrator 不包含 engine-specific 业务分支，改为通过 driver capability 与 driver 对象分发。

#### Scenario: oauth_proxy 会话启动
- **WHEN** orchestrator 启动 oauth_proxy 会话
- **THEN** 仅根据 capability/driver 注册结果执行
- **AND** orchestrator 中不出现 `if engine == ...` 分支

#### Scenario: cli_delegate 会话启动
- **WHEN** orchestrator 启动 cli_delegate 会话
- **THEN** method 与输入分发由 capability/driver 决定
- **AND** transport 状态机语义保持不变

### Requirement: 鉴权日志与状态语义 MUST 保持兼容
系统 MUST 在重构后保持现有 transport 日志目录与状态字段语义兼容。

#### Scenario: 兼容快照输出
- **WHEN** 客户端读取 auth session snapshot
- **THEN** 现有关键字段（transport/status/auth_method/provider_id/log_root）语义不回归

### Requirement: Gemini 鉴权成功判定 MUST 以 CLI 输出锚点为准
系统 MUST 仅依据 Gemini CLI 输出锚点判定委托编排鉴权会话成功，不以 auth 文件存在性作为成功条件。

#### Scenario: 授权码提交后主界面锚点出现
- **WHEN** 会话已提交 authorization code
- **AND** 输出再次出现 `Type your message or @path/to/file`
- **THEN** 会话状态转为 `succeeded`

#### Scenario: auth-status 语义保持解耦
- **WHEN** Gemini 委托编排会话进入任意状态
- **THEN** 既有 `GET /v1/engines/auth-status` 判定逻辑保持不变
- **AND** 不要求与会话状态实时联动

### Requirement: Gemini 委托编排 MUST 具备 URL 可观测能力
系统 MUST 在解析到 Gemini OAuth URL 后将其暴露在会话快照中，支持 UI 可点击展示。

#### Scenario: URL 跨行折断
- **WHEN** Gemini CLI 将授权 URL 以多行输出
- **THEN** 系统拼接并清洗后返回有效 URL 字符串

### Requirement: iFlow 鉴权成功判定 MUST 以 CLI 输出锚点为准
系统 MUST 仅依据 iFlow CLI 输出锚点判定委托编排鉴权会话成功，不以 auth 文件存在性作为成功条件。

#### Scenario: 提交授权码后主界面锚点出现
- **WHEN** iFlow 会话已提交 authorization code
- **AND** 输出出现主界面锚点 `输入消息或@文件路径`
- **THEN** 会话状态转为 `succeeded`

#### Scenario: auth-status 保持解耦
- **WHEN** iFlow 委托编排会话进入任意状态
- **THEN** 既有 `GET /v1/engines/auth-status` 判定逻辑保持不变
- **AND** 不要求与该会话状态实时联动

### Requirement: iFlow 委托编排 MUST 具备菜单选中项可观测与纠偏能力
系统 MUST 识别鉴权菜单当前选中项（`● n.`），并在非第一项时自动调整至第一项。

#### Scenario: 菜单默认选中非第一项
- **WHEN** 检测到菜单选中项为 `n > 1`
- **THEN** 系统自动注入方向键将选中项移动到第 1 项
- **AND** 再注入回车进入 OAuth 流程

### Requirement: iFlow 委托编排 MUST 暴露可访问的 OAuth URL
系统 MUST 从 iFlow OAuth 页提取 URL，并在会话快照中返回供 UI 展示。

#### Scenario: URL 被换行折断
- **WHEN** OAuth URL 以多行输出
- **THEN** 系统进行拼接与清洗后返回有效 URL 字符串

### Requirement: 系统 MUST 提供鉴权会话状态可观测语义
系统 MUST 为鉴权会话提供稳定状态集和字段语义，供 UI 与 API 统一消费。

#### Scenario: 查询会话状态快照
- **WHEN** 客户端查询会话状态
- **THEN** 响应包含 `session_id`、`engine`、`status`、`expires_at`
- **AND** 状态值属于 `starting|waiting_user|succeeded|failed|canceled|expired`

#### Scenario: 会话 challenge 可见
- **WHEN** 会话进入 `waiting_user`
- **THEN** 若解析到 challenge，响应包含 `auth_url` 与 `user_code`
- **AND** 未解析到 challenge 时返回 `null` 并提供错误摘要字段

### Requirement: 鉴权完成后 auth-status MUST 一致联动
系统 MUST 保证会话终态与 `GET /v1/engines/auth-status` 的 `auth_ready` 语义一致。

#### Scenario: 鉴权成功联动
- **WHEN** Codex `auth_code_or_url`（OpenAI device-code）会话状态为 `succeeded`
- **THEN** `GET /v1/engines/auth-status` 中 `engines.codex.auth_ready` 为 `true`

#### Scenario: 鉴权失败或取消不误报
- **WHEN** 会话状态为 `failed|canceled|expired`
- **THEN** 系统不应将该会话直接视为鉴权成功
- **AND** `auth_ready` 仅由真实凭据状态决定

### Requirement: 会话快照 MUST 暴露 auth_method 可观测字段
系统 MUST 在 auth session snapshot 中返回 `auth_method`。

#### Scenario: status 查询
- **WHEN** 客户端查询会话状态
- **THEN** 响应包含 `transport`
- **AND** 响应包含 `auth_method`
- **AND** 响应包含 `execution_mode`

### Requirement: waiting_orchestrator MUST 仅用于 CLI 委托路径
系统 MUST 将 `waiting_orchestrator` 限制在 `cli_delegate` 的自动操作阶段。

#### Scenario: oauth_proxy 路径
- **WHEN** 会话 `transport=oauth_proxy`
- **THEN** 状态不得为 `waiting_orchestrator`

#### Scenario: cli_delegate 路径
- **WHEN** 会话 `transport=cli_delegate`
- **THEN** 允许 `waiting_orchestrator` 表示后端自动输入进行中

### Requirement: browser callback 与 manual fallback MUST 可审计
系统 MUST 在 snapshot 中区分自动回调与手工兜底。

#### Scenario: callback 自动成功
- **WHEN** browser callback 成功
- **THEN** `oauth_callback_received=true`
- **AND** `oauth_callback_at` 为有效时间戳
- **AND** `manual_fallback_used=false`

#### Scenario: 手工 input 完成
- **WHEN** 用户通过 `/input` 完成授权闭环
- **THEN** `manual_fallback_used=true`

### Requirement: auth_code_or_url 协议阶段 MUST 可观测
系统 MUST 在 `auth_code_or_url` 会话中提供用户可操作信息。

#### Scenario: waiting_user with device code
- **WHEN** 会话为 `auth_method=auth_code_or_url` 且 `status=waiting_user`
- **THEN** snapshot 包含可访问的 `auth_url`（verification URL）
- **AND** `user_code` 可见

### Requirement: OpenCode Google oauth_proxy 会话 MUST 遵循 oauth_proxy 状态机语义
系统 MUST 保障该链路不会进入 `waiting_orchestrator`。

#### Scenario: 正常等待授权
- **WHEN** 会话已生成 auth URL 并等待用户完成浏览器授权
- **THEN** 状态为 `waiting_user`

#### Scenario: 手工输入已提交
- **WHEN** 用户通过 input 提交 URL/code 且已被接受
- **THEN** 状态为 `code_submitted_waiting_result` 或直接 `succeeded`

#### Scenario: 禁止 CLI 专属状态
- **WHEN** 会话 `transport=oauth_proxy`
- **THEN** 快照中不应出现 `waiting_orchestrator`

### Requirement: 自动回调与手工兜底 MUST 可审计
系统 MUST 在会话审计字段中记录回调方式与结果。

#### Scenario: 自动回调成功
- **WHEN** listener 成功接收并完成回调
- **THEN** `audit.auto_callback_listener_started=true`
- **AND** `audit.auto_callback_success=true`
- **AND** `audit.callback_mode="auto"`

#### Scenario: 手工 fallback 成功
- **WHEN** 用户通过 input 完成流程
- **THEN** `audit.manual_fallback_used=true`
- **AND** `audit.callback_mode="manual"`

### Requirement: 单账号覆盖写盘结果 MUST 可观察
系统 MUST 在会话审计字段记录 Google 单账号覆盖写盘结果摘要。

#### Scenario: 覆盖写盘成功
- **WHEN** token exchange 完成并写盘
- **THEN** 审计中包含账号覆盖成功标记（如 `audit.google_antigravity_single_account_written=true`）

### Requirement: 鉴权会话日志 MUST 按 transport 分目录管理
系统 MUST 将鉴权会话日志按 `transport + session_id` 分目录组织，避免多 transport 混写。

#### Scenario: oauth_proxy 日志目录
- **WHEN** 创建 `oauth_proxy` 会话
- **THEN** 日志写入 `data/engine_auth_sessions/oauth_proxy/<session_id>/`
- **AND** 至少包含 `events.jsonl` 与 `http_trace.log`

#### Scenario: cli_delegate 日志目录
- **WHEN** 创建 `cli_delegate` 会话
- **THEN** 日志写入 `data/engine_auth_sessions/cli_delegate/<session_id>/`
- **AND** 至少包含 `events.jsonl`、`pty.log`、`stdin.log`

### Requirement: 系统 MUST 提供标准化鉴权事件流
系统 MUST 记录统一 `events.jsonl` 事件，覆盖状态迁移、输入、回调与终态。

#### Scenario: 状态迁移写事件
- **WHEN** 会话状态从一个节点迁移到另一个节点
- **THEN** 系统写入 `state_changed` 事件
- **AND** 事件包含 `from/to/transport/timestamp`

### Requirement: transport 状态机约束 MUST 可观测
系统 MUST 在快照与事件中体现 transport 专属状态机约束，便于自动化检测。

#### Scenario: oauth_proxy 禁止 waiting_orchestrator
- **WHEN** 会话 `transport=oauth_proxy`
- **THEN** 快照状态不允许为 `waiting_orchestrator`
- **AND** 若出现则记录 `driver_error` 并进入 `failed`

#### Scenario: cli_delegate 禁止 polling_result
- **WHEN** 会话 `transport=cli_delegate`
- **THEN** 快照状态不允许为 `polling_result`
- **AND** 若出现则记录 `driver_error` 并进入 `failed`

### Requirement: UI MUST 以统一状态窗口展示会话关键字段
系统 MUST 在管理 UI 中统一展示 `engine/transport/auth_method/status/auth_url/user_code/expires_at/error`，并根据状态决定显隐。

#### Scenario: waiting_user 状态展示
- **WHEN** 会话状态为 `waiting_user`
- **THEN** 若存在 `auth_url` 则显示授权链接
- **AND** 若会话要求输入则显示输入框与提示

### Requirement: 输入提示 MUST 与引擎语义匹配
系统 MUST 根据 `transport + engine + provider_id + auth_method + input_kind` 提示正确输入语义，避免误导操作。

#### Scenario: callback 模式提示
- **WHEN** `auth_method=callback`
- **THEN** UI 提示自动回调优先，异机可粘贴回调 URL 兜底

#### Scenario: auth_code_or_url 模式提示
- **WHEN** `auth_method=auth_code_or_url`
- **THEN** UI 对 `gemini/iflow/opencode-google` 显示针对性提示
- **AND** device-code 场景仅在会话声明输入需求时显示输入框

### Requirement: UI 能力矩阵 MUST 由后端上下文注入
系统 MUST 通过后端注入 `auth_ui_capabilities` 驱动菜单渲染，避免前端硬编码能力矩阵漂移。

#### Scenario: 渲染能力矩阵
- **WHEN** `/ui/engines` 页面渲染
- **THEN** 模板上下文包含 `auth_ui_capabilities`
- **AND** 菜单项完全由该对象与 provider 列表计算

### Requirement: Auth runtime core MUST 保持 engine-agnostic
`server/runtime/auth/**` MUST 不直接依赖 `server/engines/**`，并且 MUST 不包含按引擎名称分支的业务逻辑。

#### Scenario: runtime auth 静态守卫
- **WHEN** 运行 runtime auth 静态守卫测试
- **THEN** 不存在 `server/engines` 导入
- **AND** 不存在 `if engine ==` / `if engine in (...)` 分支

### Requirement: Shared auth 协议模块 MUST 位于 engines/common
跨引擎复用的鉴权协议模块（如 OpenAI 协议）MUST 位于 `server/engines/common/**`，而非 runtime 目录。

#### Scenario: OpenAI 协议复用
- **WHEN** `codex` 与 `opencode` 复用 OpenAI OAuth/device 协议
- **THEN** 通过 `server/engines/common/openai_auth/*` 导入

### Requirement: callback completion MUST 使用 channel 路由
callback 收口 MUST 以 `channel + state` 路由到目标会话与 handler，runtime 不暴露按引擎命名的 callback API。

#### Scenario: callback 进入 manager
- **WHEN** callback 端点调用 runtime callback completer
- **THEN** 统一按 `channel` 消费 state 并定位会话
- **AND** token exchange 与凭据写盘由引擎 handler 负责

### Requirement: Session finalization MUST 由 engine runtime handler 承担
终态清理（listener 停止、state 清理、provider-specific rollback）MUST 由 engine runtime handler 承担，manager 只做统一调度与收口。

#### Scenario: 会话进入终态
- **WHEN** 任一引擎会话进入 terminal 状态
- **THEN** manager 调用 handler finalize hook
- **AND** manager 统一执行 session store 清理与全局锁释放
