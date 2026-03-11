## ADDED Requirements

### Requirement: Jobs API MUST expose dedicated debug bundle route
系统 MUST 提供独立的 debug bundle 下载接口，不通过 query 参数复用普通 bundle 路由。

#### Scenario: download debug bundle from jobs api
- **WHEN** 客户端请求 `GET /v1/jobs/{request_id}/bundle/debug`
- **AND** run 处于可下载状态
- **THEN** 响应返回 debug bundle zip 文件
- **AND** 不影响 `GET /v1/jobs/{request_id}/bundle` 的普通 bundle 语义
