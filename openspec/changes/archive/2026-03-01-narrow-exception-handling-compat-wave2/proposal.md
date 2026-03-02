## Why

上一轮治理后，`server/` 内 `except Exception` 已降至 209 处，但热点仍集中在 runtime/auth/engine 关键路径，仍存在 `pass/return` 型吞没和定位成本高的问题。需要开启新一轮“可收窄优先 + 保守兼容”的继续收敛，在不改变外部语义的前提下进一步降低风险面。

## What Changes

- 以“可确定不改语义”的场景为第一优先级继续收窄 broad catch（类型转换、JSON/I-O 解析、可识别系统调用异常）。
- 对必须保留的 broad catch 统一补充策略语义（边界映射或 best-effort cleanup）和结构化日志字段。
- 面向热点文件分波次推进（engine auth 协议、run store、runtime/auth 清理链路），每波都执行回归测试与门禁。
- 继续使用 allowlist 作为硬约束，并在每波完成后下调基线，防止回升。

## Capabilities

### New Capabilities
- _None._

### Modified Capabilities
- `exception-handling-hardening`: 在既有异常治理能力上继续收敛，补充“可收窄优先 + 保守兼容 + 基线递减”的增量约束。

## Impact

- Affected code:
  - `server/engines/common/openai_auth/common.py`
  - `server/services/orchestration/run_store.py`
  - `server/engines/*/auth/protocol/*.py`
  - `server/runtime/auth/*`（仅在可兼容前提下继续收敛）
  - `docs/contracts/exception_handling_allowlist.yaml`
  - `tests/unit/test_no_unapproved_broad_exception.py`（仅在规则需要扩展时）
- Public API: 无 breaking change。
- Runtime schema/invariants: 不修改。
- Compatibility: 默认保守兼容，不主动改变成功/失败语义。
