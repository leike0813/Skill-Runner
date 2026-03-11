## ADDED Requirements

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
