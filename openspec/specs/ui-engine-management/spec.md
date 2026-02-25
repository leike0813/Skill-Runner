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

