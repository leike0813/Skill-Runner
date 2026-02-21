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
示例客户端 MUST 通过状态与事件流持续观测运行，并在 `waiting_user` 状态支持 pending/reply 交互，直到 run 进入终态。

#### Scenario: waiting_user 交互回复
- **WHEN** 运行进入 `waiting_user`
- **THEN** 客户端展示 pending 问题
- **AND** 用户可提交 reply 并继续推进运行

#### Scenario: 终态收敛
- **WHEN** 运行进入 `succeeded|failed|canceled`
- **THEN** 客户端停止继续交互
- **AND** 展示终态结果入口

### Requirement: 示例客户端 MUST 提供 run 实时观测的可重复进入入口
示例客户端 MUST 为每个在客户端创建过的 run 提供稳定入口，允许用户在关闭页面后再次进入实时观测与对话页面。

#### Scenario: 从客户端 UI 再次进入已创建 run
- **WHEN** 用户在客户端中曾创建过某个 `request_id`
- **THEN** 用户可在客户端 Runs 入口找到该 `request_id`
- **AND** 点击后可重新打开该 run 的实时观测页面

#### Scenario: 回放作为观测页子功能
- **WHEN** 用户位于某个 run 的实时观测页面
- **THEN** 页面提供 Replay 子功能入口
- **AND** Replay 不作为再次进入 run 的唯一入口

### Requirement: 示例客户端 MUST 提供结果解包与可视化展示
示例客户端 MUST 在终态后读取结果与产物信息，并以用户可读形式展示最终输出。

#### Scenario: 结果与产物展示
- **WHEN** 运行进入终态且结果可读取
- **THEN** 客户端展示结构化结果内容
- **AND** 展示可访问的产物列表与下载入口（如有）

### Requirement: 结果页文件树与预览 MUST 复用管理 UI run 观测交互模式
示例客户端结果页中的 bundle 文件树与文件预览 MUST 与内建管理 UI run 观测页保持同构交互（树结构、滚动容器、点击加载预览）。

#### Scenario: 同构文件树/预览交互
- **WHEN** 用户进入某个 run 的结果页
- **THEN** 页面左侧展示可滚动的 bundle 文件树，右侧展示预览窗口
- **AND** 点击文件节点后，预览区域按局部渲染方式加载对应文件内容/状态

### Requirement: 示例客户端 MUST 提供录制回放 MVP 能力
示例客户端 MUST 支持将关键执行链路请求/响应记录为结构化会话文件，并提供回放视图按步骤展示关键交互结果。

#### Scenario: 录制关键交互会话
- **WHEN** 用户执行一次完整或部分运行流程（创建/上传/pending/reply/结果读取）
- **THEN** 客户端生成一份结构化录制文件
- **AND** 录制内容包含时间戳、请求摘要、响应摘要与关键状态

#### Scenario: 单步回放
- **WHEN** 用户在回放视图加载一份已录制会话
- **THEN** 客户端按步骤展示会话中的关键交互与状态变化
- **AND** 用户可单步推进查看每一步结果

### Requirement: 系统 MUST 提供 E2E 示例客户端 UI 设计参考文档
系统 MUST 提供并维护示例客户端 UI 设计参考文档，用于约束信息架构、页面布局与交互状态表达。

#### Scenario: UI 参考文档可用
- **WHEN** 开发者查阅示例客户端设计约束
- **THEN** 可以在 `docs/e2e_example_client_ui_reference.md` 获取页面结构、关键组件和状态说明
- **AND** 文档内容可用于实现与测试对齐

