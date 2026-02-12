## Purpose
定义 Web UI 中 Engine 管理与 Model Manifest 管理的行为，确保用户可查看状态、执行升级并可视化查看/补录模型快照。

## Requirements

### Requirement: UI MUST 提供 Engine 状态总览页面
系统 MUST 在 UI 提供 Engine 管理页面，显示引擎可用性与版本号。

#### Scenario: 打开 Engine 管理页
- **WHEN** 用户访问 `/ui/engines`
- **THEN** 页面显示 `codex/gemini/iflow` 状态
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
