## Why

wave4 后，`server/` 范围 broad catch 基线为 `97`，剩余高密度主要集中在 `schema_validator`、`agent_cli_manager`、`run_audit_service`。这些文件仍存在可收窄的 deterministic 分支与少量 broad-catch fallback，继续影响根因可诊断性与 allowlist 收敛速度，因此需要进入 wave5 做“可收窄优先 + 保守兼容”的增量治理。

## What Changes

- 聚焦 `server/services/platform/schema_validator.py`，将可判定的 schema 读取/解析/校验异常从 broad catch 收窄到具体异常类别。
- 聚焦 `server/services/orchestration/agent_cli_manager.py`，收窄 bootstrap/settings/path 处理中的 broad catch，并保持现有降级语义不变。
- 聚焦 `server/services/orchestration/run_audit_service.py`，收窄事件重放/解析与文件读取中的 broad catch，保留必要的兼容 fallback。
- 同步更新 `docs/contracts/exception_handling_allowlist.yaml` 基线，保持“只降不升”。
- 通过 AST 门禁与目标回归测试，防止新增未授权 broad catch。

## Capabilities

### New Capabilities
- _None._

### Modified Capabilities
- `exception-handling-hardening`: 增加 wave5 对 platform/orchestration 残余热点的收窄要求与基线递减约束。

## Impact

- Affected code:
  - `server/services/platform/schema_validator.py`
  - `server/services/orchestration/agent_cli_manager.py`
  - `server/services/orchestration/run_audit_service.py`
  - `docs/contracts/exception_handling_allowlist.yaml`
  - `tests/unit/test_no_unapproved_broad_exception.py`（门禁回归）
- Public API: 无 breaking change。
- Runtime schema/invariants: 不修改。
- Compatibility: 保持现有 HTTP 错误映射、runtime 合同语义与 orchestrator 历史读取行为。
