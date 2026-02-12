# web-management-ui Specification

## Purpose
TBD - created by archiving change web-management-ui. Update Purpose after archive.
## Requirements
### Requirement: 系统 MUST 提供 `/ui` 管理界面用于技能可视化管理
系统 MUST 暴露 `/ui` 页面，用户可在页面中查看当前已安装技能列表。

#### Scenario: 打开管理界面
- **WHEN** 用户访问 `/ui`
- **THEN** 系统返回可用页面
- **AND** 页面包含技能列表区域与技能包上传区域

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

