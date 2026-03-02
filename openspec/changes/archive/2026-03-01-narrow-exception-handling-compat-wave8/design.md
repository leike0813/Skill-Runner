## Context

当前 broad catch 基线（`server/`）为：
- total: 52
- pass: 8
- loop_control: 1
- return: 8
- log: 27
- other: 8

剩余点位已从集中热点转为长尾分散，主要位于：
- auth drivers（gemini/iflow/opencode）
- routers（jobs/management/temp_skill_runs/skill_packages/oauth_callback）
- orchestration 辅助模块
- platform/skill 辅助模块

wave8 的策略是 closeout：一次性扫清可收窄项，最大限度压缩保留项。

## Goals / Non-Goals

**Goals:**
- 一次性清理残余 `pass/loop/return/other` 吞没型 broad catch。
- 对 `log` 型 broad catch 做全量判定与收窄，收敛到最小可审计保留集合。
- 更新 allowlist 至 wave8 终态基线并通过门禁。

**Non-Goals:**
- 不修改 HTTP API 契约。
- 不修改 runtime schema/invariants。
- 不借本波引入额外重构主题（仅聚焦异常治理）。

## Decisions

### 1) Closeout 分批顺序
1. 吞没型残余优先清零（`pass/loop/return/other`）
2. `log` 型 broad catch 全量收窄评估
3. 保留项注释与结构化诊断统一化
4. allowlist 终态封板 + 门禁/回归

### 2) 收窄策略矩阵
- parse/decode：`json.JSONDecodeError`、`ValueError`、`TypeError`
- file/path：`OSError`、`FileNotFoundError`、`UnicodeDecodeError`
- third-party boundary：仅在无法稳定枚举时保留 broad catch，并记录结构化诊断

### 3) 终态保留策略
- 保留 broad catch 必须满足：
  - 有兼容性注释（为何不能继续收窄）
  - 有 `component/action/error_type/fallback` 诊断字段
  - 在 allowlist 中可审计
- 若无法满足，必须继续收窄，不允许“默认保留”。

### 4) 验证门禁
- `tests/unit/test_no_unapproved_broad_exception.py`
- 触达模块回归（auth adapters / routers / orchestration / platform / skill）
- 若触达 runtime 行为，执行 AGENTS.md runtime 必跑清单

## Risks / Trade-offs

- [Risk] 一次性 sweep 改动面大，回归风险上升。  
  → Mitigation: 先清吞没型、再清日志型，按批次跑对应测试。

- [Risk] 过度收窄导致边界异常外抛。  
  → Mitigation: 兼容边界允许受控保留 broad catch，但必须可审计。

- [Risk] 终态 allowlist 统计遗漏导致门禁失败。  
  → Mitigation: 变更后立即重算并更新 allowlist，再跑 AST 门禁。

## Migration Plan

1. 按批次完成收窄并执行同批测试。  
2. 全量完成后更新 allowlist 到 wave8 终态基线。  
3. 运行 AST 门禁 + 聚合回归；必要时追加 runtime 必跑清单。  
4. 完成后进入归档前验证。  

## Open Questions

- _None._
