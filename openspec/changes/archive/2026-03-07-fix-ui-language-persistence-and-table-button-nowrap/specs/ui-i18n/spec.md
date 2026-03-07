## ADDED Requirements

### Requirement: 语言选择 MUST 在跨页面导航中保持
系统 MUST 在用户通过 `?lang=` 显式切换语言时持久化该选择，并在后续页面导航中继续生效。

#### Scenario: 管理 UI 语言跨页保持
- **WHEN** 用户在管理 UI 任意页面选择 `lang=ja`
- **AND** 继续跳转到 `/ui` 下其他页面
- **THEN** 页面继续使用日语渲染
- **AND** 不回落到默认语言

#### Scenario: E2E 客户端语言跨页保持
- **WHEN** 用户在 E2E 客户端页面选择 `lang=fr`
- **AND** 跳转到其他 E2E 页面
- **THEN** 页面继续使用法语渲染
- **AND** 不回落到默认语言

### Requirement: 语言切换链接 MUST 保留原有查询参数
系统 MUST 在生成语言切换链接时保留当前页面已有查询参数，并仅覆盖 `lang` 参数值。

#### Scenario: 切换语言时保留页面状态参数
- **WHEN** 当前 URL 包含附加查询参数（例如筛选、分页参数）
- **AND** 用户点击语言切换
- **THEN** 新 URL 保留原有查询参数
- **AND** 仅 `lang` 值被替换
