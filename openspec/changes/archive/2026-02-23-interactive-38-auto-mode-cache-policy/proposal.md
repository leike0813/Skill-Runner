## Why

当前缓存策略在常规链路与临时 skill 链路之间不一致：临时链路被强制全量绕过缓存，而产品要求是仅 `interactive` 模式绕过缓存，`auto` 模式应可复用缓存结果。  
同时，临时 skill 若启用缓存，必须将“用户上传的 skill 压缩包”纳入缓存键，否则会出现不同 skill 包误命中同一缓存的问题。

## What Changes

- 调整临时 skill 执行缓存策略：从“始终 bypass cache”改为“仅 `interactive` bypass；`auto` 允许 cache lookup/write-back”。
- 补充临时 skill 的 cache key 组成：在常规链路键因子（inline 输入、文件输入、参数、引擎选项）基础上，额外加入上传 skill 压缩包整体哈希。
- 收敛全链路缓存模式策略：常规链路与临时链路统一为 `interactive` 不读不写缓存、`auto` 才参与缓存（仍受 `no_cache` 显式禁用约束）。
- 缓存存储隔离：常规执行链路与临时 skill 执行链路使用独立缓存表，避免跨链路缓存污染。
- 同步修订 repair-success 缓存语义：仅在缓存可用模式（`auto`）下写入缓存。
- 增补对应文档与测试，覆盖模式分流和临时包哈希参与 key 的行为。

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `ephemeral-skill-upload-and-run`: 临时 skill 链路缓存策略由全量绕过改为按执行模式分流，并新增临时包哈希参与 auto 模式 cache key。
- `mixed-input-protocol`: 明确常规链路缓存仅对 `auto` 模式生效，`interactive` 模式不进行 cache lookup/write-back。
- `output-json-repair`: `repair-success` 的“可缓存”语义改为仅在缓存可用模式下生效，避免与 interactive 禁用缓存策略冲突。

## Impact

- Affected code:
  - `server/routers/temp_skill_runs.py`
  - `server/services/cache_key_builder.py`
  - `server/routers/jobs.py`（策略一致性与守护）
  - `tests/api_integration/test_temp_skill_runs_api.py`
  - `tests/engine_integration/run_engine_integration_tests.py`
  - `tests/unit/*cache*` / `tests/unit/test_v1_routes.py`（新增或调整断言）
- Affected APIs:
  - `POST /v1/temp-skill-runs/{request_id}/upload`（cache 行为与 `cache_hit` 语义）
  - 常规 `/v1/jobs` 相关缓存语义文档（行为不变但规格显式化）
- Risk:
  - 临时链路启用缓存后，若 key 组成不完整会产生误命中；通过“压缩包哈希 + 既有输入因子”降低风险。
