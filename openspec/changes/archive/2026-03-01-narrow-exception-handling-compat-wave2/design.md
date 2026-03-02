## Context

当前 `server/` broad catch 基线为：
- total: 209
- pass: 21
- loop_control: 3
- return: 34
- log: 52
- other: 99

热点集中在 `server/routers/engines.py`、`server/routers/ui.py`、`server/engines/common/openai_auth/common.py`、`server/services/orchestration/run_store.py` 及多引擎 auth protocol 路径。上一轮已完成 router 边界统一映射与 `base_execution_adapter` 收窄，本轮进入“剩余高价值点继续收敛”。

## Goals / Non-Goals

**Goals**
- 在不改变对外语义的前提下继续降低 broad catch 总量与高风险吞没点。
- 优先清理 `pass/return` 型吞没，再处理 `other` 类型的可收窄分支。
- 对保留 broad catch 的路径补齐“可解释性 + 可诊断性”。
- 每波次结束后执行门禁并下调基线。

**Non-Goals**
- 不引入 breaking API 变更。
- 不改 runtime schema/invariants。
- 不一次性重写整段复杂 auth 协议流程（仅做可验证的局部收敛）。

## Decisions

### 1) Wave-based narrowing order
1. `server/engines/common/openai_auth/common.py`  
2. `server/services/orchestration/run_store.py`  
3. `server/engines/*/auth/protocol/*.py`  
4. 补充收尾：`runtime/auth` 与其他 residual 热点

### 2) Narrowing decision table
- `except Exception` around conversion: narrow to `TypeError/ValueError/OverflowError`
- parse-only JSON path: narrow to `json.JSONDecodeError` (+ `TypeError` if input type uncertain)
- OS/system calls: narrow to `OSError` (+ specific subclasses if obvious)
- cleanup/finalizer fallback: may retain broad catch with explicit best-effort annotation

### 3) Compatibility guardrails
- 保持原失败码、错误出口和 fallback 顺序。
- 对保留 broad catch 的路径补结构化日志字段：
  - `component`
  - `action`
  - `error_type`
  - `fallback`

### 4) Governance ratchet
- 每个波次合并前运行 AST 门禁。
- 波次完成后更新 `docs/contracts/exception_handling_allowlist.yaml` 为最新更低基线。

## Risks / Trade-offs

- [Risk] 过度收窄导致未知第三方异常穿透。  
  → Mitigation: 边界层保留 broad catch + structured diagnostics。

- [Risk] 大文件多分支导致行为漂移。  
  → Mitigation: 小步提交、按波次跑目标回归 + runtime 必跑清单。

- [Risk] 基线更新不及时导致门禁失真。  
  → Mitigation: 每波次完成后立即同步 allowlist。

## Validation Strategy

每波次至少执行：
1. `tests/unit/test_no_unapproved_broad_exception.py`
2. 对应模块单测（例如 engine auth / run_store / runtime auth）
3. runtime 必跑清单（AGENTS.md 定义）

