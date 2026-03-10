## ADDED Requirements

### Requirement: Run Observation MUST provide manual protocol rebuild action
管理 UI Run Observation 页面 MUST 提供“重构协议”按钮，供人工触发审计重构。

#### Scenario: user triggers protocol rebuild
- **WHEN** 用户点击“重构协议”
- **THEN** 页面调用管理 API 触发重构
- **AND** 显示重构结果摘要（attempt 数、written 数、备份目录、mode）

### Requirement: Run Observation default read path MUST stay replay-only
管理 UI 常规加载 MUST 保持审计回放语义，不因该按钮能力而自动重构。

#### Scenario: page load without click
- **WHEN** 用户未触发“重构协议”
- **THEN** 页面仅按现有方式读取协议历史
- **AND** 不触发重构任务
