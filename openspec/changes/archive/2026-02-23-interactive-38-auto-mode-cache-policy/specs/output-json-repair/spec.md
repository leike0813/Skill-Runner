## MODIFIED Requirements

### Requirement: Repair-success 结果 MUST 可缓存
对于 repair 后成功且 schema 通过的结果，系统 MUST 在缓存可用前提下允许写入 cache（`execution_mode=auto` 且 `no_cache!=true`）。

#### Scenario: Repair-success 缓存（auto）
- **WHEN** run 通过 deterministic repair 达到 success
- **AND** run 以 `execution_mode=auto` 执行
- **AND** `runtime_options.no_cache` is not `true`
- **THEN** 系统记录 cache entry
- **AND** 后续相同请求可命中该结果

#### Scenario: Repair-success 不缓存（interactive）
- **WHEN** run 通过 deterministic repair 达到 success
- **AND** run 以 `execution_mode=interactive` 执行
- **THEN** 系统不得写入 cache entry
