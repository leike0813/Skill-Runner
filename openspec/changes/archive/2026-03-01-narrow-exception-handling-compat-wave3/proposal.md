## Why

上一波完成后，`server/` 范围内 broad catch 基线已降至 `162`，但热点仍集中在 engine auth runtime/orchestration 链路（例如 `engine_auth_flow_manager` 与多引擎 `runtime_handler`）。这些路径中仍有 `pass/return` 吞没与可进一步类型化的分支，继续影响故障可诊断性与后续收敛效率。

## What Changes

- 在“可收窄优先 + 保守兼容”原则下继续收窄 wave3 目标文件中的 `except Exception`：
  - 优先处理 `pass/silent return` 及可明确类型边界的 parse/convert/cleanup 分支。
  - 对必须保留的 broad catch 统一补充策略注释与结构化日志上下文。
- 针对 auth runtime/orchestration 热点做分波次治理，避免一次性大改导致语义漂移。
- 继续执行 allowlist 基线递减策略，并在同一波次完成门禁校验与基线更新。
- 保持 delta-spec 工作方式：只记录本波 requirement 增量，不复制既有完整 spec。

## Capabilities

### New Capabilities
- _None._

### Modified Capabilities
- `exception-handling-hardening`: 在既有治理规范上追加 wave3 的“runtime/auth hotspot 优先收窄 + baseline 继续递减”要求。

## Impact

- Affected code:
  - `server/services/orchestration/engine_auth_flow_manager.py`
  - `server/engines/*/auth/runtime_handler.py`
  - `server/services/ui/ui_shell_manager.py`（仅可安全收窄分支）
  - `docs/contracts/exception_handling_allowlist.yaml`
  - `tests/unit/test_no_unapproved_broad_exception.py`（规则不变时仅回归）
- Public API: 无 breaking change。
- Runtime schema/invariants: 不修改。
- Compatibility: 默认兼容优先，不主动改变成功/失败语义与错误出口。
