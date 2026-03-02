## Why

wave3 后，`server/` 范围 broad catch 基线已降到 `134`，但高占比仍集中在 router 边界层（`routers/engines.py`、`routers/ui.py`）与 orchestration 读写链路（`job_orchestrator.py`）。这些路径中的 `other` 型 broad catch 仍抬高故障定位成本，需要继续执行“可收窄优先 + 保守兼容”的增量收敛。

## What Changes

- 以 router 热点为主轴继续收窄可判定 broad catch：
  - 优先处理可类型化的校验/解析/转换分支。
  - 对需要保留的边界映射 catch 统一补齐结构化诊断语义。
- 审查 `job_orchestrator` 中仍可安全收窄的广泛捕获分支，避免 silent fallback。
- 按波次执行门禁与回归，并同步下调 allowlist 基线，确保统计只降不升。
- 保持 delta-spec 方式：只写 requirement 增量，不复制主规格全文。

## Capabilities

### New Capabilities
- _None._

### Modified Capabilities
- `exception-handling-hardening`: 增加 wave4 的 router-boundary hotspot 收敛和基线递减约束。

## Impact

- Affected code:
  - `server/routers/engines.py`
  - `server/routers/ui.py`
  - `server/services/orchestration/job_orchestrator.py`
  - `docs/contracts/exception_handling_allowlist.yaml`
  - `tests/unit/test_no_unapproved_broad_exception.py`（仅回归/门禁）
- Public API: 无 breaking change。
- Runtime schema/invariants: 不修改。
- Compatibility: 维持既有 HTTP 错误映射与 runtime 行为语义。
