# builtin-e2e-example-client Specification

## Purpose
定义内建 E2E 示例客户端的独立端口部署、低耦合边界和自测能力约束。
## Requirements
### Requirement: 系统 MUST 提供独立端口运行的内建 E2E 示例客户端服务
系统 MUST 提供一套与主服务分离的示例客户端服务，用于 E2E 测试和演示，且该服务 MUST 以独立端口启动。

#### Scenario: 示例客户端独立启动
- **WHEN** 启动示例客户端服务
- **THEN** 服务在独立端口提供页面访问能力
- **AND** 不影响主服务已有端口与路由

#### Scenario: 端口配置默认与环境变量回退
- **WHEN** 未设置 `SKILL_RUNNER_E2E_CLIENT_PORT`
- **THEN** 示例客户端使用默认端口 `9814`
- **AND** 当设置了有效环境变量值时，服务使用该值覆盖默认端口

### Requirement: 示例客户端 MUST 以独立目录实现并保持低耦合边界
示例客户端代码 MUST 独立于 `server/` 目录组织，并仅通过公开 HTTP API 与后端交互，不直接依赖 `server` 内部业务实现。

#### Scenario: 独立目录部署
- **WHEN** 查看示例客户端服务代码结构
- **THEN** 示例客户端位于独立目录（非 `server/`）
- **AND** 具备独立 app 入口与路由/模板组织

#### Scenario: HTTP 协议边界
- **WHEN** 客户端执行 Skill 列表读取、运行创建、交互回复与结果读取
- **THEN** 客户端通过后端公开 API 完成调用
- **AND** 不直接 import `server` 内部 service/registry 实现

### Requirement: 示例客户端 MUST 支持 Skill 初始化读取与规格解析
示例客户端 MUST 在连接后端后读取可用 Skill 列表、描述以及输入/参数规格，用于构建执行表单。

#### Scenario: 读取 Skill 列表与详情
- **WHEN** 用户进入示例客户端首页
- **THEN** 客户端请求后端 Skill 列表与详情
- **AND** 页面展示 skill 名称、描述与可执行入口

### Requirement: 示例客户端 MUST 支持动态执行输入（inline + file）
示例客户端 MUST 根据 Skill 规格提示用户填写 inline 输入和参数，并在存在文件输入时提供上传入口。

#### Scenario: 动态渲染执行表单
- **WHEN** 用户选择某个 Skill 执行
- **THEN** 客户端按该 Skill 的 input/parameter 规格渲染输入区
- **AND** 对 file 类型输入展示上传控件

### Requirement: 示例客户端 MUST 模拟真实前端提交链路
示例客户端 MUST 在提交前执行输入校验，并按真实前端流程打包并发送执行请求。

#### Scenario: 提交前校验失败
- **WHEN** 用户提交执行但缺少必填输入或格式不合法
- **THEN** 客户端阻止提交
- **AND** 页面显示可读的校验错误信息

#### Scenario: 提交并创建运行
- **WHEN** 用户提交有效输入
- **THEN** 客户端按约定调用创建运行与上传接口
- **AND** 页面跳转到运行观测视图

### Requirement: 示例客户端 MUST 支持交互式对话直到终态
The example client MUST present a product-style chat experience while preserving FCMP interaction semantics.

#### Scenario: waiting_user 时从 pending 驱动 reply
- **WHEN** 运行进入 `waiting_user`
- **THEN** 客户端通过 pending 接口获取 `interaction_id/prompt`
- **AND** 用户提交 reply 后继续推进运行

#### Scenario: assistant ask_user YAML 转提示卡
- **WHEN** `assistant.message.final` 文本包含 `<ASK_USER_YAML>` 或 fenced `ask_user_yaml`
- **THEN** 客户端将其解析为提示卡（prompt/interaction_id/kind/options/required_fields）
- **AND** YAML 原文不渲染为聊天气泡

#### Scenario: user.input.required 作为 Agent 问询语义
- **WHEN** 客户端接收 `user.input.required`
- **THEN** 问询信息进入提示卡语义（非 System）
- **AND** 不以独立 system 气泡重复展示
- **AND** 与提示卡按 `interaction_id + prompt` 去重

#### Scenario: reply.accepted 回放用户消息
- **WHEN** 客户端接收 `interaction.reply.accepted` 且数据包含 `response_preview`
- **THEN** 客户端按 user 侧气泡渲染该回复
- **AND** 重进页面后仍可从 history 回放用户消息

#### Scenario: 终态产物摘要追加
- **WHEN** 运行进入终态且 `has_result=true` 或 `has_artifacts=true`
- **THEN** 客户端在聊天区追加 Agent 侧最终摘要消息
- **AND** `conversation.completed` 不渲染为独立聊天气泡
- **AND** 若终态 `assistant.message.final` 为结构化 done 结果（`__SKILL_DONE__=true`），该原始消息不重复渲染
- **AND** 若首次拉取 `final-summary` 未就绪，客户端重试直到成功或达到上限

### Requirement: 示例客户端观察页 MUST 去除技术诊断噪音
观察页 MUST 聚焦对话与基础状态，不展示后台诊断细节面板。

#### Scenario: 页面不渲染技术面板
- **WHEN** 用户访问 `/runs/{request_id}`
- **THEN** 页面不展示 `stderr`、`diagnostics`、`Event Relations`、`Raw Ref Preview`
- **AND** 页面仅保留对话区、提示卡、回复输入区与状态信息

### Requirement: 示例客户端回复输入 MUST 支持快捷键发送
观察页回复输入框 MUST 支持 `Ctrl+Enter`/`Cmd+Enter` 发送，并提示该快捷键。

#### Scenario: 快捷键触发发送
- **WHEN** 用户在回复输入框按下 `Ctrl+Enter` 或 `Cmd+Enter`
- **THEN** 客户端执行与点击发送按钮等价的 reply 请求
- **AND** 按钮右侧显示快捷键提示

### Requirement: 示例客户端 MUST 提供 run 实时观测的可重复进入入口
示例客户端 MUST 提供稳定的 runs 入口，允许用户在关闭页面后再次进入实时观测与对话页面。

#### Scenario: 从客户端 UI 再次进入已创建 run
- **WHEN** 用户访问客户端 runs 页面
- **THEN** 用户可在客户端 Runs 入口找到该 `request_id`
- **AND** 点击 `Details` 后可重新打开该 run 的实时观测页面

#### Scenario: Replay 路由下线
- **WHEN** 客户端调用历史 Replay 路由（`/recordings*`、`/api/recordings*`、`/api/runs/{request_id}/observe-summary`）
- **THEN** 系统不再提供该能力（路由移除）

### Requirement: 示例客户端 MUST 提供结果解包与可视化展示
示例客户端 MUST 在 Observation 页面内展示终态结果摘要与文件树预览能力，不再依赖独立 Result 页面。  
文件树预览数据 MUST 来自后端 jobs 文件接口返回的 canonical 预览载荷，客户端 MUST NOT 本地解压 bundle 并自行构建预览内容。

#### Scenario: Observation 终态结果与产物展示
- **WHEN** 运行进入终态且结果可读取
- **THEN** 客户端在 Observation 对话区追加结构化结果摘要
- **AND** 展示可访问的产物信息（如有）

#### Scenario: Observation 文件树/预览交互
- **WHEN** 用户在 Observation 页展开文件树
- **THEN** 页面展示固定双栏文件树与预览窗口
- **AND** 点击文件节点后，预览区按局部渲染加载内容
- **AND** 预览内容来源为后端返回的 canonical preview payload

#### Scenario: E2E 与管理 UI 预览语义一致
- **WHEN** 同一路径文件在管理 UI 与 E2E 页面被打开
- **THEN** 两侧使用同源预览载荷语义
- **AND** 不因客户端本地依赖差异导致 markdown/json 渲染分叉

### Requirement: 系统 MUST 提供 E2E 示例客户端 UI 设计参考文档
系统 MUST 提供并维护示例客户端 UI 设计参考文档，用于约束信息架构、页面布局与交互状态表达。

#### Scenario: UI 参考文档可用
- **WHEN** 开发者查阅示例客户端设计约束
- **THEN** 可以在 `docs/e2e_example_client_ui_reference.md` 获取页面结构、关键组件和状态说明
- **AND** 文档内容可用于实现与测试对齐

### Requirement: 示例客户端文件树 MUST 默认目录折叠

示例客户端 Observation 页文件树 MUST 与管理 UI 一致，默认目录折叠并支持点击展开/收起。

#### Scenario: observation file tree starts collapsed
- **WHEN** 用户打开 `/runs/{request_id}`
- **THEN** 文件树目录默认折叠
- **AND** 用户展开目录后才显示子节点

### Requirement: 示例客户端 run explorer data MUST respect backend denylist filtering

示例客户端显示的 run 文件树与预览 MUST 基于后端过滤后的结果，不得在前端重新放宽可见集合。

#### Scenario: ignored paths never rendered in client tree
- **WHEN** 后端返回的 run 文件树已应用 debug 黑名单过滤
- **THEN** 客户端 MUST 仅渲染返回结果
- **AND** 命中黑名单的目录（例如 `node_modules`）不得出现在页面

### Requirement: Release compose MUST preserve optional E2E client topology
系统 MUST 在 release compose 资产中保留与本地 compose 一致的可选 `e2e_client` 服务块（默认注释），并继续采用同镜像双入口模式。

#### Scenario: Optional e2e_client remains commented
- **WHEN** 用户下载 release compose 资产
- **THEN** `api` 为默认启用服务
- **AND** `e2e_client` 服务保持默认注释并附带启用提示

#### Scenario: Enabling e2e_client uses same image
- **WHEN** 用户按注释提示启用 `e2e_client`
- **THEN** `e2e_client` 与 `api` 使用同一镜像 tag
- **AND** 仅通过入口命令区分服务角色

### Requirement: 示例客户端 Run Observation MUST 提供 bundle 下载入口
示例客户端 MUST 在 Run Observation 页面提供可直接下载当前 run bundle 的入口，并继续提供独立的 debug bundle 下载入口；两者均不依赖 runtime options 中的 debug 开关。

#### Scenario: user downloads run bundle from observation page
- **WHEN** 用户在 `/runs/{request_id}` 页面点击下载 bundle
- **THEN** 浏览器开始下载 zip 文件
- **AND** 下载目标对应当前 run 的 bundle 内容

#### Scenario: debug bundle remains downloadable without runtime debug option
- **WHEN** 用户在 `/runs/{request_id}` 页面查看成功终态 run
- **THEN** 页面继续提供 `Download Bundle` 与 `Download Debug Bundle`
- **AND** 两个入口的可用性与 `runtime_options.debug` 无关

#### Scenario: download action does not break file explorer
- **WHEN** 用户触发 bundle 下载
- **THEN** 文件树与文件预览功能继续可用
- **AND** 页面不会被强制跳转到非 observation 页面

### Requirement: E2E 示例客户端 MUST 支持同镜像独立入口启动
系统 MUST 支持将 E2E 示例客户端与主服务打包到同一镜像中，并通过独立入口在单独容器服务中启动客户端。

#### Scenario: 同镜像启动 E2E 客户端
- **WHEN** 使用主服务镜像并指定 E2E 客户端入口命令启动容器
- **THEN** E2E 客户端可在独立端口提供页面服务
- **AND** 客户端仍仅通过公开 HTTP API 与后端交互

#### Scenario: 主服务入口保持默认
- **WHEN** 用户未覆盖镜像入口命令直接启动容器
- **THEN** 容器默认运行后端主服务
- **AND** E2E 客户端不会自动占用其端口

### Requirement: E2E chat renderer MUST group assistant_process events into collapsible thinking bubbles
E2E 对话区 MUST 将连续的 `assistant_process` 条目聚合为单个可折叠思考气泡。

#### Scenario: collapsed thinking bubble shows latest process line
- **GIVEN** 连续收到多条 `assistant_process`
- **WHEN** 思考气泡处于折叠状态
- **THEN** UI MUST 仅显示最后一条过程消息

### Requirement: E2E renderer MUST dedupe promoted/final content
E2E 对话区 MUST 在 `assistant_final` 到达时移除已提升的过程条目，避免重复渲染。

#### Scenario: final dedupe by message_id then normalized text
- **GIVEN** 已渲染思考条目
- **AND** 后续收到 `assistant_final`
- **WHEN** `message_id` 可用
- **THEN** UI MUST 优先按 `message_id` 删除对应过程条目
- **AND** 若 `message_id` 缺失，MUST 在同 attempt 按规范化文本精确匹配删除

### Requirement: Built-in E2E runtime options UI MUST follow context-aware visibility
E2E 客户端 runtime options 区域 MUST 仅暴露仍然有效的运行参数，不得继续展示已下线的 runtime debug 开关。

#### Scenario: runtime debug option is removed
- **WHEN** 用户查看 E2E run form 的 runtime options 区域
- **THEN** 页面 MUST NOT 显示 `debug` 相关 checkbox
- **AND** 表单提交 MUST NOT 发送 `runtime_options.debug`

### Requirement: E2E run timestamps MUST be rendered from timezone-explicit values
E2E runs 列表与 run observation 页面 MUST 使用带时区语义的时间值，以保证浏览器本地时区展示正确。

#### Scenario: e2e runs list uses timezone-explicit updated_at
- **WHEN** 用户访问 `/runs`
- **THEN** 列表中的 `updated_at` 使用带明确时区语义的时间值渲染
- **AND** 浏览器本地时区转换后不产生 UTC/本地混淆

### Requirement: E2E run form MUST submit file input values as declarative uploads-relative paths
The built-in E2E client MUST include file-sourced input values in `POST /v1/jobs` payload `input`, where each value is an `uploads/`-relative path.

#### Scenario: installed run submits mixed inline and file input values
- **WHEN** user submits a run form with both inline and file fields
- **THEN** the create-run payload includes inline values and file path values together in `input`
- **AND** each file value points to the uploaded zip entry path relative to `uploads/`

### Requirement: E2E file upload zip MUST preserve original filenames under field folders
The built-in E2E client MUST package uploaded files under `<field>/<original_filename>` entries instead of renaming them to schema keys.

#### Scenario: uploaded file keeps original filename
- **WHEN** user uploads `input.txt` for field `input_file`
- **THEN** upload zip contains `input_file/input.txt`
- **AND** `input.input_file` is set to `input_file/input.txt`

### Requirement: E2E file preview MUST consume unified line-numbered rendered html
E2E Observation 文件预览 MUST 优先消费后端统一生成的 `rendered_html`，并在除 Markdown 外的可显示文本预览中显示行号。

#### Scenario: preview jsonl file in e2e observation
- **WHEN** 用户在 Observation 页面打开 `.jsonl` 文件
- **THEN** 页面显示 JSONL 语义渲染内容
- **AND** 行号与后端预览结果保持一致

#### Scenario: markdown preview stays rich-text only
- **WHEN** 用户打开 Markdown 文件
- **THEN** 页面显示富文本 Markdown
- **AND** 不额外追加源码行号栏

### Requirement: E2E Run Observation MUST expose normal/debug bundle downloads
E2E 客户端 Run Observation 页面 MUST 提供普通 bundle 与 debug bundle 两个并列下载动作，且仅在成功终态可用。

#### Scenario: e2e shows both bundle actions
- **WHEN** 用户打开 `/runs/{request_id}`
- **THEN** 页面显示 `Download Bundle` 与 `Download Debug Bundle` 两个按钮
- **AND** 两者样式一致

#### Scenario: e2e bundle actions enabled only on success
- **WHEN** run 状态为 `queued/running/waiting_* /failed/canceled`
- **THEN** 两个下载按钮不可用
- **WHEN** run 状态变为 `succeeded`
- **THEN** 两个下载按钮可用

### Requirement: E2E runs list MUST support pagination with return-context preservation
E2E runs 列表 MUST 支持分页，且从详情返回时应保留进入前分页上下文。

#### Scenario: return to same page after opening run detail
- **WHEN** 用户在 runs 第 N 页进入某 run 详情并返回
- **THEN** 页面回到第 N 页
- **AND** 分页参数与页大小保持不变

### Requirement: E2E Run Form MUST expose hard timeout runtime option with validated non-negative integer input

E2E 示例客户端的 Run Form MUST 始终显示 `hard_timeout_seconds` 输入控件，并在提交前校验其为非负整数。

#### Scenario: run form shows hard timeout spinbox
- **WHEN** 用户打开 installed skill 或 fixture skill 的 run form
- **THEN** 页面显示 `hard_timeout_seconds` 输入控件
- **AND** 该控件使用 number spinbox
- **AND** 设置 `min=0`
- **AND** 设置 `step=60`

#### Scenario: invalid hard timeout input is rejected
- **WHEN** 用户提交的 `hard_timeout_seconds` 为空、负数、非整数或包含小数
- **THEN** 客户端阻止提交
- **AND** 页面返回可读校验错误

#### Scenario: valid hard timeout is submitted explicitly
- **WHEN** 用户提交合法的 `hard_timeout_seconds`
- **THEN** 客户端在 create-run 请求中显式写入 `runtime_options.hard_timeout_seconds`
- **AND** 该值为整数

### Requirement: E2E Run Form MUST prefill hard timeout from skill default then service default

E2E 示例客户端 MUST 按稳定优先级预填 `hard_timeout_seconds`，优先 skill runtime default，缺失时回退服务级默认值。

#### Scenario: installed skill default wins
- **WHEN** installed skill detail 包含 `runtime.default_options.hard_timeout_seconds`
- **THEN** run form 预填该值

#### Scenario: fixture skill default wins
- **WHEN** fixture skill manifest 包含 `runtime.default_options.hard_timeout_seconds`
- **THEN** run form 预填该值

#### Scenario: service default fallback is used
- **WHEN** skill 未提供 `runtime.default_options.hard_timeout_seconds`
- **THEN** run form 使用 management runtime options 接口返回的服务默认值作为预填
