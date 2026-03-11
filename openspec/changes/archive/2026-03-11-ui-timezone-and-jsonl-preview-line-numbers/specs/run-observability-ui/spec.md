## ADDED Requirements

### Requirement: Run observation timestamps MUST be rendered from timezone-explicit values
Run 观测相关页面 MUST 基于带明确时区语义的时间值进行展示，前端再按浏览器本地时区渲染，避免把 UTC naive 字符串误当成本地时间。

#### Scenario: management run list/detail use timezone-explicit timestamps
- **WHEN** 管理 UI 渲染 `/ui/runs` 或 `/ui/runs/{request_id}`
- **THEN** 页面消费的时间值具备明确时区语义
- **AND** 浏览器本地时区转换后的展示结果与原 UTC 时间一致可推导

### Requirement: Run file preview MUST support line-numbered text rendering including jsonl
Run 文件预览 MUST 支持 `jsonl` 语义渲染，并且除 Markdown 外的可显示文本预览 MUST 带行号。

#### Scenario: preview jsonl file in run detail
- **WHEN** 用户在 run 详情页打开 `.jsonl` 文件
- **THEN** 预览以 JSONL 语义渲染内容
- **AND** 每个可显示文本行带行号

#### Scenario: markdown remains rich render without source line numbers
- **WHEN** 用户在 run 详情页打开 Markdown 文件
- **THEN** 页面继续显示富文本渲染结果
- **AND** 不强制显示源码行号
