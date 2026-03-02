## Why

wave5 后，`server/` 范围 broad catch 基线已降至 `84`，但高密度残余仍集中在 runtime observability、skill patching 与 trust-folder adapter 路径。上述模块继续存在可收窄的 deterministic 异常分支，影响故障归因效率与 allowlist 收敛节奏，因此需要进入 wave6 做增量治理。

## What Changes

- 聚焦 `server/runtime/observability/run_observability.py`，收窄可判定的文件读取/解析/转换 broad catch，保持历史与 cursor 兼容语义。
- 聚焦 `server/services/skill/skill_patcher.py`，收窄 patch 流水线中可类型化异常并保留兼容 fallback。
- 聚焦 `server/engines/gemini/adapter/trust_folder_strategy.py` 与 `server/engines/codex/adapter/trust_folder_strategy.py`，收窄 deterministic 路径处理异常。
- 对必须保留的边界 broad catch 补齐结构化诊断字段（`component/action/error_type/fallback`）。
- 同步更新 `docs/contracts/exception_handling_allowlist.yaml` 基线并通过 AST 门禁与回归测试。

## Capabilities

### New Capabilities
- _None._

### Modified Capabilities
- `exception-handling-hardening`: 增加 wave6 在 runtime-observability / skill / trust-folder adapter 热点上的收窄约束与基线递减要求。

## Impact

- Affected code:
  - `server/runtime/observability/run_observability.py`
  - `server/services/skill/skill_patcher.py`
  - `server/engines/gemini/adapter/trust_folder_strategy.py`
  - `server/engines/codex/adapter/trust_folder_strategy.py`
  - `docs/contracts/exception_handling_allowlist.yaml`
  - `tests/unit/test_no_unapproved_broad_exception.py`（门禁回归）
- Public API: 无 breaking change。
- Runtime schema/invariants: 不修改。
- Compatibility: 保持 FCMP/RASP 事件语义、history/cursor 读取行为与 skill patch 输出契约不变。
