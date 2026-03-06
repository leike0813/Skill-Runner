## ADDED Requirements

### Requirement: 管理 UI Run Detail MUST 提供协议流双视图
系统 MUST 在 Run Detail 的 FCMP、RASP、Orchestrator 三个协议面板中默认展示摘要气泡视图，并支持独立切换到 raw 视图。

#### Scenario: 默认摘要视图
- **WHEN** 用户打开 `/ui/runs/{request_id}`
- **THEN** 三个协议面板默认展示摘要气泡
- **AND** 不直接默认展示完整 JSON 原文

#### Scenario: 切换 raw 视图
- **WHEN** 用户勾选某协议面板的 `View raw`
- **THEN** 该面板显示原始结构化 JSON 文本
- **AND** 取消勾选后恢复摘要气泡视图

### Requirement: 管理 UI 文件预览 MUST 支持格式化渲染
系统 MUST 在 Skill Browser 与 Run Detail 文件预览中支持 Markdown 和 JSON 的格式化显示。

#### Scenario: Markdown 预览
- **WHEN** 预览文件被判定为 `markdown`
- **THEN** 页面显示安全清洗后的 HTML 渲染

#### Scenario: JSON 预览
- **WHEN** 预览文件被判定为 `json`
- **THEN** 页面显示格式化后的 JSON 文本
