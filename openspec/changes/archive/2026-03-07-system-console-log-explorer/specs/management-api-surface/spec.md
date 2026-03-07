## ADDED Requirements

### Requirement: 管理 API MUST 提供系统日志查询接口
管理 API MUST 提供 `GET /v1/management/system/logs/query`，用于查询系统日志与 bootstrap 日志，并支持关键词、级别、时间范围过滤与 cursor 分页。

#### Scenario: query system log with filters
- **WHEN** 客户端请求 `/v1/management/system/logs/query?source=system&limit=200&q=error&level=ERROR`
- **THEN** 响应包含 `items/next_cursor/total_matched/source`
- **AND** 返回项仅来自 `skill_runner.log*` 日志族

#### Scenario: query bootstrap log with cursor paging
- **WHEN** 客户端请求 `/v1/management/system/logs/query?source=bootstrap&cursor=200&limit=200`
- **THEN** 响应返回 bootstrap 日志分页结果
- **AND** `next_cursor` 可用于继续拉取下一页
