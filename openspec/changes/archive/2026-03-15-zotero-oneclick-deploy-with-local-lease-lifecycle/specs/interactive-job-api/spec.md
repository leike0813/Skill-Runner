## ADDED Requirements

### Requirement: 本地运行模式 MUST 支持插件租约心跳生命周期
系统在 `SKILL_RUNNER_RUNTIME_MODE=local` 下 MUST 提供 lease acquire/heartbeat/release API，以支持插件进程生命周期对本地服务进行保活和回收控制。

#### Scenario: local lease acquire and heartbeat
- **GIVEN** runtime mode is `local`
- **WHEN** 客户端调用 `POST /v1/local-runtime/lease/acquire`
- **THEN** 系统返回 `lease_id`、`ttl_seconds`、`expires_at`
- **AND** 后续 `heartbeat` 可续期同一 lease

#### Scenario: lease expiry triggers local shutdown
- **GIVEN** 本地服务已出现过至少一个 lease
- **AND** 当前所有 lease 已过期或被释放
- **WHEN** 超过 TTL 且无新 lease
- **THEN** 系统触发本地服务自停

#### Scenario: lease API rejected outside local mode
- **WHEN** runtime mode is not `local`
- **THEN** `acquire/heartbeat/release` 接口返回 `409`
