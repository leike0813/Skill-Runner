## ADDED Requirements

### Requirement: local runtime lease MUST provide first-heartbeat grace window
系统在 local runtime lease 生命周期中 MUST 提供首次心跳宽限窗口，以覆盖慢启动阶段的首次心跳延迟；该能力不得改变现有 lease API 字段结构。

#### Scenario: lease does not expire during first-heartbeat grace
- **GIVEN** 客户端刚完成 `POST /v1/local-runtime/lease/acquire`
- **AND** 尚未发送首次 heartbeat
- **WHEN** 过期判定发生在 `ttl + first_heartbeat_grace` 窗口内
- **THEN** 系统不得将该 lease 判定为过期

#### Scenario: post-first-heartbeat returns to normal ttl
- **GIVEN** lease 已收到首次 heartbeat
- **WHEN** 后续过期判定执行
- **THEN** 系统按常规 TTL 续租语义判定过期
- **AND** 不再应用首次心跳宽限
