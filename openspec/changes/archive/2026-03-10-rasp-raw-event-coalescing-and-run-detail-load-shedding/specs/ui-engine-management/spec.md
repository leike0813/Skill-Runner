## ADDED Requirements

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
