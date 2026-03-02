## Context

当前 broad catch 基线（`server/`）为：
- total: 134
- pass: 14
- loop_control: 3
- return: 22
- log: 49
- other: 46

wave3 已完成 auth runtime/orchestration 主干收敛，剩余热点主要是 router 边界层：
- `server/routers/engines.py`: total 18（other 16）
- `server/routers/ui.py`: total 13（other 13）
- `server/services/orchestration/job_orchestrator.py`: total 6（log 5, other 1）

## Goals / Non-Goals

**Goals:**
- 降低 router 热点中的 `other` broad catch 占比，并保持统一边界映射风格。
- 在不改变行为语义前提下，收窄可判定异常域（validation/parse/convert paths）。
- 对必须保留的边界 catch 补齐结构化诊断字段和 fallback 语义。
- 完成 allowlist 基线递减并通过门禁测试。

**Non-Goals:**
- 不改 HTTP API 协议与状态码契约。
- 不改 runtime schema/invariants。
- 不做跨模块大规模重构，仅做可验证的局部收敛。

## Decisions

### 1) Wave4 收敛顺序
1. `server/routers/engines.py`
2. `server/routers/ui.py`
3. `server/services/orchestration/job_orchestrator.py`
4. allowlist 与门禁回归

理由：先处理 broad catch 密度最高的边界层文件，再处理 orchestrator 余量，可获得最大净降幅并降低行为风险。

### 2) 边界层收窄规则
- 可确定输入校验/类型转换异常：收窄到 `ValueError/TypeError`
- 资源/文件路径读取：收窄到 `OSError`（必要时联合 `ValueError`）
- 统一错误出口：保留 `except Exception` 仅用于 boundary mapping，并通过统一 helper 输出结构化日志

### 3) 兼容护栏
- 不改现有 `HTTPException` 状态码与 detail 语义。
- 不改变 orchestrator 状态推进、seq/history 行为。
- 每个波次必须通过 AST 门禁 + router/orchestrator 回归 + runtime 必跑清单。

## Risks / Trade-offs

- [Risk] 过度收窄导致边界未知异常直接外抛。  
  → Mitigation: 边界层保留统一 broad catch 出口，仅对可判定分支先行收窄。

- [Risk] router 端错误映射细节变化引起前端兼容问题。  
  → Mitigation: 保持原状态码和 detail 文本，新增仅限诊断上下文字段。

- [Risk] 基线下降后遗漏 allowlist 更新导致门禁误报。  
  → Mitigation: 将 allowlist 更新设为独立任务，并在最终前单独回跑门禁。

## Migration Plan

1. 按 wave4 任务顺序逐文件收窄并保留兼容边界行为。  
2. 每个文件完成后立即跑目标测试；波次结束后跑全套门禁。  
3. 统计新基线并同步 `exception_handling_allowlist.yaml`。  
4. 若出现语义回归，按文件粒度回滚，不影响已验证模块。  

## Open Questions

- _None._
