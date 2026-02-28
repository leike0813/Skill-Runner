# management-api-surface Specification

## Purpose
TBD - created by archiving change interactive-27-unified-management-api-surface. Update Purpose after archive.
## Requirements
### Requirement: 系统 MUST 提供统一管理 API 面
系统 MUST 提供前端无关的管理 API，覆盖 Skill 管理、Engine 管理、Run 管理三类资源。

#### Scenario: 管理 API 资源分组
- **WHEN** 客户端查询管理能力
- **THEN** 可在统一命名空间访问 Skill / Engine / Run 管理资源
- **AND** 返回稳定 JSON 字段，不依赖 HTML 结构

### Requirement: Run 管理 MUST 支持对话窗口所需动作
系统 MUST 提供 Run 对话窗口最小动作集合：状态、文件浏览、实时输出、交互回复。

#### Scenario: 查询 Run 会话状态
- **WHEN** 客户端调用 Run 管理状态接口
- **THEN** 响应包含 `status`
- **AND** 包含 `pending_interaction_id`（可空）
- **AND** 包含交互计数字段（如 `interaction_count`）

#### Scenario: 读取 Run 文件树与预览
- **WHEN** 客户端请求 Run 文件树与文件预览
- **THEN** 系统返回可用于对话窗口侧边栏展示的结构化数据
- **AND** 路径越界请求被拒绝

#### Scenario: 消费 Run 实时输出
- **WHEN** 客户端连接 Run 管理实时输出接口
- **THEN** 系统提供 stdout/stderr 增量事件流
- **AND** 支持断线后续传

#### Scenario: 处理 pending/reply
- **WHEN** Run 进入 `waiting_user`
- **THEN** 客户端可通过管理 API 获取 pending 内容并提交 reply
- **AND** 回复后 Run 可继续推进到下一状态

#### Scenario: 主动终止 Run
- **WHEN** 客户端调用 Run 管理取消动作
- **THEN** 系统执行与执行域一致的 cancel 语义
- **AND** 对活跃 run 返回可观测终态（`canceled`）
- **AND** 对终态 run 保持幂等响应

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

### Requirement: Skill 管理接口 MUST 返回可枚举的有效引擎集合
系统 MUST 在 Skill 管理相关接口中返回可供前端直接枚举的 `effective_engines`，并保留声明字段用于解释来源。

#### Scenario: 显式 allow-list 与 deny-list
- **WHEN** Skill 同时声明 `engines` 与 `unsupported_engines`
- **THEN** 管理接口返回计算后的 `effective_engines`
- **AND** 返回原始声明字段（`engines`、`unsupported_engines`）供前端展示

#### Scenario: 缺失 engines 的默认枚举
- **WHEN** Skill 未声明 `engines`
- **THEN** 管理接口将系统支持引擎减去 `unsupported_engines` 后作为 `effective_engines` 返回
- **AND** 前端无需自行推断默认引擎集合

### Requirement: Run 管理 MUST 支持协议审计历史读取
系统 MUST 提供可按协议流查询 run 历史事件的管理接口，支持审计和排障场景。

#### Scenario: 读取协议历史
- **WHEN** 客户端调用 `GET /v1/management/runs/{request_id}/protocol/history`
- **AND** 提供 `stream=fcmp|rasp|orchestrator`
- **THEN** 响应包含 `request_id`、`stream`、`attempt`、`available_attempts`、`count`、`events`
- **AND** `events` 仅包含对应协议流记录

#### Scenario: 应用历史过滤参数
- **WHEN** 客户端提供 `from_seq/to_seq/from_ts/to_ts`
- **THEN** 接口按过滤条件返回事件子集

#### Scenario: 按 attempt 切换审计历史
- **WHEN** 客户端调用 `GET /v1/management/runs/{request_id}/protocol/history` 并提供 `attempt`
- **THEN** 系统返回该轮次事件
- **AND** 返回 `available_attempts` 供前端翻页
- **AND** 对 `stream=fcmp`，`events[].seq` 使用全局序号，attempt 本地序号位于 `events[].meta.local_seq`
- **AND** 对 `stream=rasp|orchestrator`，`events[].seq` 仍表示该 attempt 内本地序号

#### Scenario: orchestrator 旧数据缺失 seq 仍可读取
- **WHEN** 旧审计文件中的 orchestrator 事件缺失 `seq`
- **THEN** 系统按文件顺序回填序号后返回
- **AND** 不因缺失 `seq` 导致事件被静默过滤

#### Scenario: 非法 stream 参数被拒绝
- **WHEN** `stream` 参数不在 `fcmp|rasp|orchestrator` 中
- **THEN** 接口返回 `400`

### Requirement: 管理日志区间读取 MUST 支持按 attempt 定位
系统 MUST 在 `GET /v1/management/runs/{request_id}/logs/range` 支持 `attempt` 参数，以保障 raw_ref 回跳和轮次审计一致。

#### Scenario: 指定 attempt 读取日志片段
- **WHEN** 客户端调用 `logs/range` 并提供 `attempt`
- **THEN** 系统从 `.audit/*.{attempt}.log` 读取并返回区间内容

### Requirement: Engine 模型接口 MUST 支持 provider 维度元数据并保持兼容
系统 MUST 在现有模型列表接口中提供 provider 维度元数据，同时保持 `models[].id` 的既有语义与兼容性。

#### Scenario: opencode 模型列表返回 provider/model
- **WHEN** 客户端请求 `GET /v1/engines/opencode/models`
- **THEN** 返回的模型项中 `id` 保持 `provider/model`
- **AND** 每个模型项额外包含 `provider` 与 `model` 字段

#### Scenario: 非 opencode 引擎兼容
- **WHEN** 客户端请求其他引擎模型列表
- **THEN** 原有字段语义保持不变
- **AND** 旧客户端仅读取 `models[].id` 不受影响

### Requirement: 鉴权公开 API MUST 保持兼容
系统 MUST 在本次内部重构中保持现有 `/v1/engines/auth/*` 公开 API 路径与主要请求/响应语义兼容。

#### Scenario: 兼容 oauth_proxy 与 cli_delegate 接口
- **WHEN** 客户端调用 `/v1/engines/auth/oauth-proxy/sessions*` 或 `/v1/engines/auth/cli-delegate/sessions*`
- **THEN** 接口路径与主要字段语义保持不变

#### Scenario: 兼容旧 sessions 接口
- **WHEN** 客户端调用 `/v1/engines/auth/sessions*` 兼容层
- **THEN** 兼容行为保持可用
- **AND** 内部可转发到重构后的 façade/orchestrator

### Requirement: 鉴权会话输入 MUST 统一使用 input 接口
系统 MUST 使用 `/input` 统一承载授权码、回调 URL 与 API key 输入，不再使用 submit 子动作。

#### Scenario: 提交统一输入
- **WHEN** 客户端调用 `POST /v1/engines/auth/sessions/{session_id}/input`
- **AND** 请求体包含 `kind` 与 `value`
- **THEN** 系统分发输入到对应会话并返回最新快照

#### Scenario: 非法输入类型
- **WHEN** `kind` 不在 `code|api_key|text` 集合
- **THEN** 返回 `422`

#### Scenario: submit 端点废弃
- **WHEN** 客户端调用 `POST /v1/engines/auth/sessions/{session_id}/submit`
- **THEN** 返回 `404` 或 `405`

### Requirement: 鉴权会话 MUST 使用统一 auth_method 新语义
系统 MUST 使用 `callback|auth_code_or_url|api_key` 表达鉴权方式，并拒绝历史值。

#### Scenario: 新语义有效
- **WHEN** 客户端在 start 请求中传入 `auth_method=callback|auth_code_or_url|api_key`
- **THEN** 会话按 capability 矩阵创建并进入对应状态机

#### Scenario: 旧语义拒绝
- **WHEN** 客户端传入历史值（如 `browser-oauth`、`device-auth`）
- **THEN** 返回 `422`

### Requirement: OpenAI 鉴权矩阵 MUST 按新语义暴露
系统 MUST 为 `codex` 与 `opencode/provider=openai` 暴露 `callback` 与 `auth_code_or_url` 两种方式，并兼容两种 transport。

#### Scenario: codex 组合可启动
- **WHEN** `engine=codex` 且 `transport in {oauth_proxy,cli_delegate}` 且 `auth_method in {callback,auth_code_or_url}`
- **THEN** 会话成功创建并进入非终态

#### Scenario: opencode/openai 组合可启动
- **WHEN** `engine=opencode`、`provider_id=openai`、`transport in {oauth_proxy,cli_delegate}`、`auth_method in {callback,auth_code_or_url}`
- **THEN** 会话成功创建并进入非终态

### Requirement: OpenAI callback 流 MUST 支持自动回调与手工兜底
系统 MUST 支持 callback 自动收口，并在回调不可达时允许 `/input` 手工提交 URL/code。

#### Scenario: callback 自动收口
- **WHEN** callback 提供合法 `state + code`
- **THEN** 会话进入 `succeeded`

#### Scenario: 手工兜底
- **WHEN** 会话处于 `waiting_user`
- **AND** 客户端调用 `POST /v1/engines/auth/sessions/{id}/input`
- **THEN** `kind=text` 可提交 redirect URL 或授权码完成闭环

### Requirement: OpenAI auth_code_or_url 协议路径 MUST 为零 CLI
系统 MUST 在 `oauth_proxy + auth_code_or_url` 路径禁止 CLI/PTY 调用。

#### Scenario: 协议代理
- **WHEN** `transport=oauth_proxy` 且 `auth_method=auth_code_or_url`（OpenAI device-code 语义）
- **THEN** 会话返回 `verification_url + user_code`
- **AND** 后端按协议轮询 token
- **AND** 不调用 CLI/PTY/subprocess

### Requirement: OpenCode provider 鉴权启动 MUST 支持 provider_id
系统 MUST 允许 OpenCode 在 start 请求中显式携带 `provider_id`，并按 provider 能力矩阵校验组合。

#### Scenario: OpenCode provider 会话启动
- **WHEN** 客户端调用 `POST /v1/engines/auth/sessions`
- **AND** 请求体包含 `engine=opencode` 与 `provider_id`
- **THEN** 系统创建会话并返回快照

### Requirement: OpenCode API Key provider MUST 通过 oauth_proxy 会话入口可见
系统 MUST 将 API Key 直写 provider 归入 `oauth_proxy` 路径的可用能力集合，避免 UI 在 oauth_proxy 下丢失 provider 入口。

#### Scenario: oauth_proxy 下显示 API key provider
- **WHEN** 客户端选择 `transport=oauth_proxy` 并发起 OpenCode 鉴权
- **THEN** API key provider 仍可被选择
- **AND** 输入类型为 `api_key`

### Requirement: OpenCode Google oauth_proxy MUST 支持 callback 与 auth_code_or_url
系统 MUST 放行 `engine=opencode`、`provider_id=google` 在 `oauth_proxy` 下的 `callback|auth_code_or_url` 两种组合。

#### Scenario: callback 组合
- **WHEN** 请求体为 `engine=opencode, transport=oauth_proxy, provider_id=google, auth_method=callback`
- **THEN** 返回 `200` 且会话进入 `waiting_user`

#### Scenario: auth_code_or_url 组合
- **WHEN** 请求体为 `engine=opencode, transport=oauth_proxy, provider_id=google, auth_method=auth_code_or_url`
- **THEN** 返回 `200` 且会话进入 `waiting_user`

### Requirement: Engine 鉴权 API MUST 提供 transport 分组路由
系统 MUST 提供按 transport 分组的鉴权会话 API，以避免 `oauth_proxy` 与 `cli_delegate` 契约混淆。

#### Scenario: 启动 oauth_proxy 会话
- **WHEN** 客户端调用 `POST /v1/engines/auth/oauth-proxy/sessions`
- **THEN** 系统创建 `oauth_proxy` 会话并返回快照
- **AND** 快照包含 `transport=oauth_proxy`

#### Scenario: 启动 cli_delegate 会话
- **WHEN** 客户端调用 `POST /v1/engines/auth/cli-delegate/sessions`
- **THEN** 系统创建 `cli_delegate` 会话并返回快照
- **AND** 快照包含 `transport=cli_delegate`

### Requirement: 回调接口 MUST 归属 oauth_proxy 路由组
系统 MUST 提供 `oauth_proxy` 专属 OpenAI callback 接口，并对 state 执行会话绑定、TTL 与一次性消费校验。

#### Scenario: 有效 state 回调成功
- **WHEN** 客户端访问 `GET /v1/engines/auth/oauth-proxy/callback/openai`
- **AND** `state/code` 匹配活跃会话
- **THEN** 会话推进到成功或明确失败终态

### Requirement: 旧鉴权会话接口 MUST 提供兼容层
系统 MUST 保留旧 `/v1/engines/auth/sessions*` 接口一个过渡周期，并保证兼容映射可用。

#### Scenario: 旧接口启动会话
- **WHEN** 客户端调用 `POST /v1/engines/auth/sessions`
- **THEN** 系统通过兼容映射转发到新分组 API
- **AND** 外部请求语义保持可用

### Requirement: 鉴权会话 V2 模型 MUST 使用 auth_method/provider_id 替代 method
系统 MUST 在 V2 会话模型中移除 `method` 历史语义，统一使用 `auth_method` 与 `provider_id`。

#### Scenario: V2 启动请求
- **WHEN** 客户端提交 `AuthSessionStartRequestV2`
- **THEN** 请求体要求显式 `transport` 与 `auth_method`
- **AND** `provider_id` 在需要 provider 的引擎场景必填

### Requirement: 管理 UI 鉴权入口 MUST 由全局 transport 统一驱动
系统 MUST 允许管理 UI 先选择全局 transport，再发起引擎鉴权会话；请求契约仍保持 `engine/transport/auth_method/provider_id`。

#### Scenario: 先选 transport 再发起鉴权
- **WHEN** 用户在 `/ui/engines` 将全局鉴权后台切换为 `cli_delegate`
- **AND** 从引擎入口菜单选择某个鉴权方式
- **THEN** UI 请求体中的 `transport` 必须为 `cli_delegate`
- **AND** 不需要在按钮层面硬编码 transport

### Requirement: 管理 UI MUST 对 OpenCode 使用 provider->auth_method 组合
系统 MUST 在 OpenCode 鉴权发起时显式提交 `provider_id` 与 `auth_method` 组合，且二者来源于当前 transport 的能力过滤结果。

#### Scenario: OpenCode 发起鉴权
- **WHEN** 用户在 OpenCode 入口中先选择 provider，再选择 auth_method
- **THEN** UI 请求体包含 `engine=opencode`、`provider_id=<selected>`、`transport=<global>`、`auth_method=<selected>`
