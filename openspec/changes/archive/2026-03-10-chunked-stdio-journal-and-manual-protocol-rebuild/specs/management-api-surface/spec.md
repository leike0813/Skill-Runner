## ADDED Requirements

### Requirement: Management API MUST expose manual protocol rebuild endpoint
系统 MUST 提供 run 级手动协议重构接口。

#### Scenario: trigger rebuild
- **WHEN** 客户端调用 `POST /v1/management/runs/{request_id}/protocol/rebuild`
- **THEN** 系统对该 run 全部 attempts 执行协议重构
- **AND** 返回重构结果摘要（含备份路径与 per-attempt 结果）
- **AND** 返回 `mode=strict_replay`

### Requirement: Rebuild endpoint MUST not alter normal history API semantics
新增重构接口 MUST 不改变 `protocol/history` 与常规页面读取语义。

#### Scenario: no rebuild call
- **WHEN** 客户端只调用 `GET /v1/management/runs/{request_id}/protocol/history`
- **THEN** 响应行为与未触发重构时一致
- **AND** 不引入隐式重构副作用
