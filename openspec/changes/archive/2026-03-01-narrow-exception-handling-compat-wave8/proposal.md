## Why

wave7 后，`server/` 范围 broad catch 基线为 `52`，剩余点位分散在 auth driver、router 边界、orchestration 辅助链路与少量 platform/skill 模块。为避免长期尾部拖延，本波以“尽量一次收口”为目标，执行全量残余清扫：可收窄全部收窄，必须保留者统一进入可审计的最小集合。

## What Changes

- 面向 `server/` 剩余 broad catch 做 closeout sweep：
  - 优先清零 `pass/loop_control/return/other` 吞没型分支。
  - 对 `log` 型 broad catch 逐条判断：能收窄则收窄，不能收窄则补齐结构化诊断与兼容注释。
- 对保留项建立“终态治理”约束：仅允许 approved contexts（boundary/best-effort/observability/third-party）且必须可解释。
- 更新 `docs/contracts/exception_handling_allowlist.yaml` 到 wave8 closeout 基线，确保“只降不升”。
- 通过 AST 门禁和多模块回归测试，确认一次性收口不引入行为回归。

## Capabilities

### New Capabilities
- _None._

### Modified Capabilities
- `exception-handling-hardening`: 增加 wave8 closeout 要求（残余 broad catch 全量收敛 + 终态可审计保留策略）。

## Impact

- Affected code: `server/` 中当前所有仍含 broad catch 的模块（重点覆盖 auth driver / routers / orchestration / platform / skill）。
- Governance:
  - `docs/contracts/exception_handling_allowlist.yaml`
  - `tests/unit/test_no_unapproved_broad_exception.py`（门禁回归）
- Public API: 无 breaking change。
- Runtime schema/invariants: 不修改。
- Compatibility: 保持 HTTP 错误映射、runtime 协议语义和历史兼容行为不变。
