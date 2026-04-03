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

#### Scenario: upgrade button is reused as install for missing engine
- **WHEN** 某 engine 在 managed prefix 下未安装
- **THEN** 表格中的现有单 engine 升级按钮文案显示为“安装”
- **AND** 点击后复用现有任务通道执行单 engine install

#### Scenario: installed engine keeps upgrade action
- **WHEN** 某 engine 已在 managed prefix 下安装
- **THEN** 同一按钮文案显示为“升级”
- **AND** 点击后执行现有 single-engine upgrade

#### Scenario: 点击全部升级
- **WHEN** 用户点击“升级全部”
- **THEN** UI 创建全引擎升级任务并展示任务状态

### Requirement: UI MUST 展示 per-engine stdout/stderr
系统 MUST 在升级状态视图中展示每个引擎的 stdout/stderr。

#### Scenario: 升级任务终态
- **WHEN** 升级任务进入 `succeeded` 或 `failed`
- **THEN** UI 显示每个引擎的执行结果
- **AND** 显示 per-engine stdout/stderr

#### Scenario: task status panel shows actual action type
- **WHEN** UI 展示单 engine 任务状态
- **THEN** 状态面板显示该 engine 本次动作是 `install` 或 `upgrade`
- **AND** 不得把 install 误标为 upgrade

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

### Requirement: UI behavior MUST remain compatible during internal module migration
系统 MUST 在 services/runtime/engines 重组期间保持管理 UI 与运行 UI 的交互语义兼容。

#### Scenario: Existing UI flows
- **WHEN** 用户执行既有 UI 流程（引擎管理、鉴权、run 观测）
- **THEN** 页面行为与接口交互语义不因内部路径调整而改变

### Requirement: UI behavior MUST remain stable under runtime port injection
即使 runtime observability/protocol 改为 ports 注入，管理 UI 的实时与历史读取行为 MUST 保持兼容。

#### Scenario: UI event/log flows after refactor
- **WHEN** 用户在 `/ui/engines`、`/ui/runs` 等页面查看实时与历史数据
- **THEN** 事件流、日志读取与状态展示语义不回归
- **AND** 内部注入失败应返回可诊断错误而非静默异常

### Requirement: UI behavior MUST remain compatible after hard cutover
phase2 删除兼容导入层后，`/ui` 路由与交互语义 MUST 保持兼容。

#### Scenario: Existing UI flows after hard cutover
- **WHEN** 用户执行既有 UI 交互流程
- **THEN** 页面行为与后端响应语义不回归

### Requirement: Built-in E2E runtime options UI MUST follow context-aware visibility
E2E 客户端 runtime options 区域 MUST 根据 run source 与 execution mode 控制可见性，避免无效配置暴露。

#### Scenario: debug_keep_temp visibility
- **WHEN** 运行链路为后端内建 skill（installed source）
- **THEN** `debug_keep_temp` 不显示
- **AND** 仅在临时上传 skill（temp source）显示该选项

#### Scenario: interactive options visibility
- **WHEN** `execution_mode != interactive`
- **THEN** `interactive_auto_reply` 与 `interactive_reply_timeout_sec` 均不显示

#### Scenario: timeout field visibility in interactive mode
- **WHEN** `execution_mode=interactive` 且 `interactive_auto_reply=false`
- **THEN** `interactive_reply_timeout_sec` 不显示
- **AND** `interactive_auto_reply` 以 checkbox 显示

#### Scenario: timeout field visible for auto reply
- **WHEN** `execution_mode=interactive` 且 `interactive_auto_reply=true`
- **THEN** 显示 `interactive_reply_timeout_sec` 输入框

### Requirement: Built-in E2E runtime option labels MUST use configured Chinese copy
E2E runtime options 展示文案 MUST 使用中文标签。

#### Scenario: Runtime option labels
- **WHEN** 用户查看 runtime options 区域
- **THEN** 文案包含：
- **AND** `no_cache=禁用缓存机制`
- **AND** `debug=Debug模式`
- **AND** `debug_keep_temp=保留上传的临时 Skill 包（Debug用）`
- **AND** `interactive_auto_reply=超时自动回复`
- **AND** `interactive_reply_timeout_sec=回复超时阈值`

### Requirement: 鉴权菜单能力矩阵 MUST 来源于统一策略文件

系统 MUST 使用后端统一策略文件生成 `/ui/engines` 的鉴权菜单能力矩阵，不得在 UI router 或模板中硬编码引擎/transport/provider 组合。

#### Scenario: render auth menu capabilities from strategy service
- **WHEN** 用户访问 `/ui/engines`
- **THEN** 后端注入的 `auth_ui_capabilities` MUST 来源于统一策略服务
- **AND** 菜单可用项 MUST 与后端启动校验能力保持一致

### Requirement: OpenCode provider 菜单 MUST 使用策略文件声明能力

系统 MUST 以策略文件中显式列举的 provider 组合作为 OpenCode 鉴权方式可用性的判定依据。

#### Scenario: provider not declared in strategy is unavailable
- **WHEN** OpenCode provider 未在策略文件声明对应 transport+methods
- **THEN** UI MUST NOT 展示该 provider 的对应鉴权方式入口

### Requirement: UI Inline TUI 进程 MUST 纳入统一 lease 治理
UI shell 启动的 ttyd/CLI 进程 MUST 注册 lease；会话停止或终态清理 MUST 释放 lease；终止路径 MUST 使用统一终止器。

#### Scenario: 停止 UI TUI 会话
- **WHEN** 用户主动停止 inline TUI
- **THEN** 系统统一终止受管进程
- **AND** lease 被关闭

### Requirement: UI inline TUI capability SHALL come from engine shell capability provider
UI shell 管理器 MUST 通过统一 capability provider 解析命令参数、sandbox 探测、安全配置与鉴权提示，并且 MUST NOT 在主流程保留 per-engine 分支。

#### Scenario: 启动 inline TUI 会话
- **WHEN** 用户选择任一 engine 启动会话
- **THEN** manager 从 capability provider 获取启动能力
- **AND** manager 不直接维护 engine-specific 规则分支

### Requirement: Engine model refresh lifecycle SHALL route through unified catalog lifecycle
Engine model refresh actions in UI MUST route through a unified catalog lifecycle registry and MUST NOT directly depend on a single-engine catalog implementation.

#### Scenario: 手动刷新 opencode models
- **WHEN** 调用 `/ui/engines/opencode/models/refresh`
- **THEN** 路由通过统一 lifecycle 调用 refresh
- **AND** 不直接 import engine 专属 catalog 对象

### Requirement: 管理 UI Run Detail MUST 提供协议流双视图
系统 MUST 在管理 UI Run Detail 协议流面板中，避免刷新时强制抢占用户滚动位置，并支持摘要到详情的逐条展开查看。

#### Scenario: 用户上翻后刷新不强制拉底
- **WHEN** 用户在某协议流面板手动滚动到非底部位置
- **AND** 系统刷新该面板数据
- **THEN** 面板滚动位置保持用户当前位置

#### Scenario: 用户贴底时刷新继续跟随
- **WHEN** 用户处于某协议流面板底部附近
- **AND** 新事件到达并刷新面板
- **THEN** 面板自动跟随到底部显示最新内容

#### Scenario: 摘要气泡展开详情
- **WHEN** 用户点击摘要气泡
- **THEN** 面板展开该条详情并显示关键字段与结构化内容
- **AND** 同一面板其余展开项自动折叠

### Requirement: 管理 UI 文件预览 MUST 支持格式化渲染
系统 MUST 在 Skill Browser 与 Run Observation 文件预览区域提供高对比可读样式，并支持常见文本格式高亮渲染。

#### Scenario: Skill Browser 长文件预览
- **WHEN** 文件内容超过预览容器高度
- **THEN** 预览区域保持固定高度并提供纵向滚动

#### Scenario: 常见格式高亮渲染
- **WHEN** 预览文件格式为 `json|yaml|toml|python|javascript`
- **THEN** 预览渲染为可读高亮视图
- **AND** 渲染失败时回退普通文本显示

### Requirement: 文件树与预览交互 MUST 使用统一复用模块
系统 MUST 在管理 Run Observation、Skill Browser 与 E2E Run 页面复用同一文件树/预览交互模块，避免页面间行为漂移。

#### Scenario: 三处页面目录折叠行为一致
- **WHEN** 用户打开文件树
- **THEN** 目录默认折叠
- **AND** 展开/收起行为在三处页面一致

### Requirement: Run Observation 布局 MUST 保持稳定可读
系统 MUST 固定三流窗口高度，并将 Raw stderr 区域改为折叠式全宽区域，避免布局随内容抖动。

#### Scenario: 三流高度不随模式变化
- **WHEN** 用户在摘要视图与 raw 视图之间切换
- **THEN** FCMP/RASP/Orchestrator 三流窗口高度保持一致

#### Scenario: 折叠 stderr 红点提示
- **WHEN** Raw stderr 处于折叠状态且存在输出
- **THEN** 折叠栏显示未读红点提示

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

### Requirement: Engine 管理页内嵌终端入口 MUST 与统一 ttyd 端口策略一致
系统 MUST 保证 Engine 管理页的内嵌终端入口与统一 `UI_SHELL_TTYD_PORT` 策略一致，不依赖固定 `7681` 常量。

#### Scenario: 默认部署访问内嵌终端
- **WHEN** 用户通过默认部署进入 `/ui/engines`
- **THEN** 内嵌终端链接使用会话返回的 `ttyd_port`
- **AND** 默认端口为 `17681`

#### Scenario: 自定义端口访问内嵌终端
- **WHEN** 用户通过环境变量修改 `UI_SHELL_TTYD_PORT`
- **THEN** 页面使用后端返回的会话端口访问 ttyd
- **AND** 不要求前端改写固定端口常量

### Requirement: Engine 管理页 MUST 在高风险鉴权选项上显示醒目风险标记
系统 MUST 在 `/ui/engines` 的鉴权方式菜单中，为高风险方法显示简短风险标记，且该标记来源于策略文件。

#### Scenario: OpenCode Google in oauth_proxy
- **GIVEN** 用户在管理页选择 `transport=oauth_proxy`
- **AND** 选择 OpenCode provider `google`
- **WHEN** 页面渲染鉴权方式菜单
- **THEN** `callback` / `auth_code_or_url` 选项 MUST 显示 `(High risk!)` 标记

#### Scenario: OpenCode Google in cli_delegate
- **GIVEN** 用户在管理页选择 `transport=cli_delegate`
- **AND** 选择 OpenCode provider `google`
- **WHEN** 页面渲染鉴权方式菜单
- **THEN** `auth_code_or_url` 选项 MUST 显示 `(High risk!)` 标记

### Requirement: 管理页鉴权方法菜单 MUST 仅使用策略能力矩阵
系统 MUST 从后端策略能力矩阵渲染 OpenCode 方法菜单，禁止前端本地 fallback 硬编码。

#### Scenario: provider transport method resolution
- **WHEN** 页面根据 provider + transport 渲染方法菜单
- **THEN** 方法列表 MUST 仅来自后端注入的 capability payload
- **AND** 当 capability 为空时 MUST 显示“无可用方式”错误，不进行本地推断

### Requirement: 管理端 System Console MUST 提供系统日志浏览能力
管理 UI MUST 在 `/ui/settings`（文案语义为 System Console）提供日志浏览模块，支持系统日志与 bootstrap 日志的查询与分页展示，并与现有日志设置、数据重置模块并存。

#### Scenario: system console shows log explorer controls
- **WHEN** 用户打开 `/ui/settings`
- **THEN** 页面显示 System Console 标题
- **AND** 显示 Log Explorer 的 source、关键词、级别、时间范围与 Load more 控件
- **AND** 不影响原有 logging settings 与 data reset 控件

### Requirement: engine auth menu MUST expose profile-driven credential import
管理 UI 的引擎鉴权菜单 MUST 支持文件导入，并由后端 profile 规则动态决定所需文件与写盘路径提示。

#### Scenario: non-opencode engines render import option
- **GIVEN** 引擎为 codex/gemini/iflow
- **WHEN** 用户打开鉴权菜单
- **THEN** UI MUST 在鉴权方式列表中提供导入入口并与原入口使用分隔符分组

#### Scenario: opencode render provider-scoped import option
- **GIVEN** 引擎为 opencode 且 provider 为 oauth provider（openai/google）
- **WHEN** 用户展开 provider 菜单
- **THEN** UI MUST 在 provider 三级菜单提供导入入口
- **AND** provider=google 时 MUST 显示高风险提示

### Requirement: management auth import spec MUST use ask_user upload_files payload
管理端导入规格接口 MUST 返回统一 `ask_user` 形状，不再返回旧 `required_files/optional_files` 双列表。

#### Scenario: import spec response shape
- **WHEN** 客户端调用 `GET /v1/management/engines/{engine}/auth/import/spec`
- **THEN** response MUST include `ask_user.kind=upload_files`
- **AND** `ask_user.files[]` MUST include `name` and optional `required/hint/accept`

### Requirement: management UI MUST render import dialog from ask_user.files
管理 UI MUST 基于后端 `ask_user` 提示渲染文件选择对话框。

#### Scenario: google high-risk notice
- **WHEN** `ask_user.ui_hints.risk_notice_required=true`
- **THEN** UI MUST show high-risk warning in import dialog

### Requirement: run detail RASP summary MUST render parsed JSON events
管理 UI Run Detail 的 RASP 摘要视图 MUST 能识别并渲染 `parsed.json` 事件。

#### Scenario: parsed json bubble summary
- **WHEN** RASP 行中存在 `event.type = parsed.json`
- **THEN** 页面摘要 MUST 展示至少 `stream` 与响应摘要（`response` 或 `summary`）
- **AND** 若存在 `session_id`，摘要 SHOULD 显示该值以便追踪会话

### Requirement: Run Detail timeline/protocol panels MUST remain stable across running-to-terminal transition
管理 UI 在 run 从 running 切换到 terminal 时，timeline 与 protocol 面板 MUST 不出现因观测口径切换导致的事件回退。

#### Scenario: user observes protocol panel across terminal transition
- **GIVEN** 用户在 Run Detail 页面持续观察同一 run
- **WHEN** run 状态从 running 变为 terminal
- **THEN** 面板数据源切换 MUST 保持事件集合稳定（除 limit 裁剪）
- **AND** MUST NOT 因 terminal 收敛而出现明显事件数量突降。

### Requirement: run detail timeline MUST be lazy-loaded and collapse-aware
管理 UI Run Detail 的 timeline 面板 MUST 在默认折叠状态下不初始化历史拉取，也不参与周期刷新。

#### Scenario: collapsed timeline on page load
- **WHEN** 用户打开 Run Detail 页面且 timeline 默认折叠
- **THEN** 页面 MUST NOT 发起 timeline 初始化请求

#### Scenario: expanded timeline
- **WHEN** 用户展开 timeline
- **THEN** 页面 MUST 拉取历史并进入增量刷新
- **AND** 折叠后 MUST 停止 timeline 刷新

### Requirement: protocol panel polling MUST use bounded queries
Run Detail 三流面板轮询 MUST 采用有界历史查询，避免全量拉取。

#### Scenario: protocol polling request
- **WHEN** 页面轮询 `protocol/history`
- **THEN** 请求 MUST include `limit` 参数（默认 200）

### Requirement: RASP panel MUST converge to audit view after terminal
Run Detail 在 run 进入 terminal 后，RASP 面板 MUST 以 audit 结果为最终渲染基线。

#### Scenario: terminal status arrives while RASP panel is open
- **WHEN** 前端收到 terminal 状态并刷新 RASP 历史
- **THEN** 面板 MUST 触发全量重取并替换临时 live 缓存
- **AND** 最终显示结果 MUST 与 audit history 一致

### Requirement: Run Observation MUST provide manual protocol rebuild action
管理 UI Run Observation 页面 MUST 提供“重构协议”按钮，供人工触发审计重构。

#### Scenario: user triggers protocol rebuild
- **WHEN** 用户点击“重构协议”
- **THEN** 页面调用管理 API 触发重构
- **AND** 显示重构结果摘要（attempt 数、written 数、备份目录、mode）

### Requirement: Run Observation default read path MUST stay replay-only
管理 UI 常规加载 MUST 保持审计回放语义，不因该按钮能力而自动重构。

#### Scenario: page load without click
- **WHEN** 用户未触发“重构协议”
- **THEN** 页面仅按现有方式读取协议历史
- **AND** 不触发重构任务

### Requirement: management run-detail chat MUST render assistant_process with collapsible thinking groups
管理 UI run detail 对话区 MUST 支持 `assistant_process` 思考气泡分组渲染，且默认折叠。

#### Scenario: management collapsible process group
- **GIVEN** chat history 包含连续 `assistant_process`
- **WHEN** 页面渲染对话区
- **THEN** UI MUST 将其聚合为单个思考气泡
- **AND** 点击后 MUST 展开显示全部过程条目

### Requirement: management and E2E MUST share core state transition while keeping independent adapters
管理 UI 与 E2E MUST 共享同一思考气泡状态机逻辑，并保留各自渲染适配器。

#### Scenario: same event sequence produces same grouping boundaries
- **GIVEN** 两端输入同一 chat replay 事件序列
- **WHEN** 运行共享状态机
- **THEN** 过程分组边界与 final 去重结果 MUST 一致
- **AND** 两端可采用不同 DOM/CSS 呈现细节

### Requirement: Management protocol history MUST expose RASP turn markers
管理端协议历史查询在 `stream=rasp` 时 MUST 可见 turn marker 审计事件。

#### Scenario: query rasp history after attempt execution
- **GIVEN** 某次 attempt 已产生回合开始与结束
- **WHEN** 调用 `GET /v1/management/runs/{request_id}/protocol/history?stream=rasp`
- **THEN** 返回事件中 MUST 包含 `agent.turn_start` 与 `agent.turn_complete`
- **AND** 事件顺序 MUST 满足 `agent.turn_start` 在 `agent.turn_complete` 之前

### Requirement: 管理端 Run Detail MUST expose parallel bundle download actions
管理 UI Run Detail MUST 显示两个并列下载按钮：`Download Bundle` 与 `Download Debug Bundle`，并保持统一按钮样式。

#### Scenario: bundle actions are parallel and style-consistent
- **WHEN** 用户打开 `/ui/runs/{request_id}`
- **THEN** 页面同时显示普通 bundle 与 debug bundle 下载按钮
- **AND** 两个按钮使用同一按钮样式类

#### Scenario: bundle/rebuild button availability follows status
- **WHEN** run 状态不是 `succeeded`
- **THEN** 两个下载按钮处于不可用状态
- **AND** `Rebuild Protocol` 在非 terminal 状态不可用

### Requirement: 管理端 Run 详情文件树 MUST refresh on attempt/terminal transitions
管理 UI MUST 在 attempt 变化和 run 进入 terminal 后刷新文件树，以保持文件视图与执行进度一致。

#### Scenario: refresh file tree on attempt changes
- **WHEN** Run 详情轮询检测到 attempt 集合变化
- **THEN** 文件树触发刷新

#### Scenario: refresh file tree on terminal settle
- **WHEN** run 从非 terminal 进入 terminal
- **THEN** 文件树至少再刷新一次

### Requirement: Engine 管理页内嵌终端在 ttyd 缺失时 MUST 前后端同时禁用
系统在 `ttyd` 不可用时 MUST 同时禁用 UI 入口和启动接口，避免用户触发不可恢复的运行时错误。

#### Scenario: ui hides TUI entry when ttyd missing
- **GIVEN** 运行环境未检测到 `ttyd` 可执行文件
- **WHEN** 用户访问 `/ui/engines` 或 `/ui/management/engines/table`
- **THEN** 页面不渲染 `Start TUI` 按钮
- **AND** 内置终端交互主面板隐藏，仅保留不可用提示

#### Scenario: tui start endpoint rejects when ttyd missing
- **GIVEN** 运行环境未检测到 `ttyd` 可执行文件
- **WHEN** 客户端调用 `POST /ui/engines/tui/session/start`
- **THEN** 后端返回 `503`
- **AND** 响应 detail 明确为依赖缺失，不再返回运行时 `500`

### Requirement: UI 首页 MUST 展示基于 ensure 缓存的引擎状态指示器
系统 MUST 在 `/ui` 首页展示引擎状态指示器，状态来源为 ensure/bootstrap 缓存快照，不执行实时 CLI 探测。

#### Scenario: ui home shows static indicator without polling
- **GIVEN** 用户访问 `/ui`
- **WHEN** 页面渲染引擎状态区块
- **THEN** 状态行按 `keys.ENGINE_KEYS` 顺序展示所有引擎
- **AND** 页面仅展示静态快照（无自动轮询刷新）

#### Scenario: ui home maps cache snapshot to led levels
- **GIVEN** 缓存快照包含 `present` 与 `version` 字段
- **WHEN** 页面计算状态灯颜色
- **THEN** `present=true` 且 `version` 非空显示绿灯
- **AND** `present=true` 且 `version` 为空显示黄灯
- **AND** `present=false` 显示红灯
