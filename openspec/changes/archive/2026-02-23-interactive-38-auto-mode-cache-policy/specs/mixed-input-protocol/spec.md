## MODIFIED Requirements

### Requirement: cache key MUST include inline input hash
缓存键 MUST 纳入 inline input 的稳定哈希，并与文件输入、参数以及引擎/运行选项共同构成请求语义指纹。

#### Scenario: cache key differs by inline payload
- **WHEN** 文件输入和 parameter 相同但 inline input 不同
- **THEN** 两次请求缓存键不同，不应误命中

#### Scenario: cache key differs by engine/runtime options
- **WHEN** inline 输入、文件输入与 parameter 相同
- **AND** 引擎相关运行选项不同
- **THEN** 两次请求缓存键不同，不应误命中

### Requirement: cache lookup and write-back MUST be auto-only
无论输入来源如何组合，系统 MUST 仅在 `execution_mode=auto` 时执行 cache lookup/write-back；`interactive` 模式 MUST 绕过缓存。

#### Scenario: regular interactive run bypasses cache
- **WHEN** 常规 run 以 `execution_mode=interactive` 提交
- **THEN** 系统不执行 cache lookup
- **AND** run 终态不写入 cache entry

#### Scenario: regular auto run keeps cache behavior
- **WHEN** 常规 run 以 `execution_mode=auto` 提交
- **AND** `runtime_options.no_cache` is not `true`
- **THEN** 系统按现有策略执行 cache lookup 与 write-back
