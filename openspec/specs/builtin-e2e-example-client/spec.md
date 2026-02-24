# builtin-e2e-example-client Specification

## Purpose
TBD - created by archiving change interactive-33-builtin-e2e-example-client. Update Purpose after archive.
## Requirements
### Requirement: 系统 MUST 提供独立端口运行的内建 E2E 示例客户端服务
系统 MUST 提供一套与主服务分离的示例客户端服务，用于 E2E 测试和演示，且该服务 MUST 以独立端口启动。

#### Scenario: 示例客户端独立启动
- **WHEN** 启动示例客户端服务
- **THEN** 服务在独立端口提供页面访问能力
- **AND** 不影响主服务已有端口与路由

#### Scenario: 端口配置默认与环境变量回退
- **WHEN** 未设置 `SKILL_RUNNER_E2E_CLIENT_PORT`
- **THEN** 示例客户端使用默认端口 `8011`
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

#### Scenario: Observation 终态结果与产物展示
- **WHEN** 运行进入终态且结果可读取
- **THEN** 客户端在 Observation 对话区追加结构化结果摘要
- **AND** 展示可访问的产物信息（如有）

#### Scenario: Observation 文件树/预览交互
- **WHEN** 用户在 Observation 页展开文件树
- **THEN** 页面展示固定双栏文件树与预览窗口
- **AND** 点击文件节点后，预览区按局部渲染加载内容

### Requirement: 系统 MUST 提供 E2E 示例客户端 UI 设计参考文档
系统 MUST 提供并维护示例客户端 UI 设计参考文档，用于约束信息架构、页面布局与交互状态表达。

#### Scenario: UI 参考文档可用
- **WHEN** 开发者查阅示例客户端设计约束
- **THEN** 可以在 `docs/e2e_example_client_ui_reference.md` 获取页面结构、关键组件和状态说明
- **AND** 文档内容可用于实现与测试对齐
