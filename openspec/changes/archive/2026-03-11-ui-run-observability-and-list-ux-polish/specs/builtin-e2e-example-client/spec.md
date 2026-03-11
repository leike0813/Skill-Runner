## ADDED Requirements

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
