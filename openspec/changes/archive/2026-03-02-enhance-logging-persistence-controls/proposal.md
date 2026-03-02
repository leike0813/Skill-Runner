## Why

当前服务已支持基础日志落盘，但主要是“控制台 + 按大小轮转”的最小能力，缺少统一配置模型、按天轮换与目录级限额治理。随着运行时间增长，日志容量和保留策略不可控，排障与运维成本持续升高。

## What Changes

- 新增统一日志策略配置（`core_config` 主导，环境变量覆盖）。
- 将应用日志文件处理器从按大小轮换改为按天轮换（`TimedRotatingFileHandler`）。
- 增加日志目录总配额治理，超限时按最旧归档优先淘汰。
- 增加可选 JSON 格式输出，默认保持文本格式。
- 明确启动失败降级路径：文件处理器初始化失败时退化为 stream-only 并记录告警。
- 增加日志策略单元测试，覆盖轮换、配额、降级和幂等行为。
- 移除 `LOG_MAX_BYTES` 语义，不再作为运行时策略输入。

## Capabilities

### New Capabilities

- `logging-persistence-controls`: 统一全局应用日志的持久化、轮换、限额与格式策略。

### Modified Capabilities

- None.

## Impact

- Affected code:
  - `server/core_config.py`
  - `server/logging_config.py`
  - `docs/dev_guide.md`
  - `docs/architecture_overview.md`
  - `docs/test_specification.md`
  - `tests/unit/test_logging_config.py`
  - `tests/unit/test_logging_quota_policy.py`
- Public API:
  - HTTP API: no change
  - runtime schema/invariants: no change
- Runtime behavior:
  - 全局应用日志策略增强，默认仍为文本输出并保留控制台日志。
