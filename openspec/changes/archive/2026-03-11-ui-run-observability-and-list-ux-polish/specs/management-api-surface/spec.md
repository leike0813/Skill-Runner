## ADDED Requirements

### Requirement: Management runs list MUST support pagination metadata
管理 API 的 run 列表 MUST 支持分页参数并返回分页元数据，默认每页 20 条。

#### Scenario: query paged management runs
- **WHEN** 客户端请求 `GET /v1/management/runs?page=2&page_size=20`
- **THEN** 响应包含当前页 runs
- **AND** 包含 `page/page_size/total/total_pages` 元数据

### Requirement: Management run summary MUST include model
管理 API 的 run 列表与 run 详情 MUST 返回 run 关联模型信息（若可用）。

#### Scenario: model is returned in run summary payload
- **WHEN** 客户端请求管理 run 列表或 run 详情
- **THEN** 响应对象包含 `model` 字段
- **AND** 缺失模型时返回空值或 `null`（不报错）
