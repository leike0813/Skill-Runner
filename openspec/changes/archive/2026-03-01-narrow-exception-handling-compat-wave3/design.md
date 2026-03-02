## Context

当前 broad catch 基线（`server/`）为：
- total: 162
- pass: 17
- loop_control: 3
- return: 24
- log: 50
- other: 68

热点仍集中在 auth runtime/orchestration 路径：`engine_auth_flow_manager`、`opencode/codex/gemini/iflow runtime_handler`、以及部分 UI shell 兼容分支。wave2 已完成 protocol flow、run_store、session_lifecycle 的收窄与基线递减，wave3 继续在不改变外部语义前提下推进可判定分支收窄。

## Goals / Non-Goals

**Goals:**
- 持续降低 broad catch 总量，优先清理 auth runtime/orchestration 里的 `pass/return` 吞没分支。
- 将可判定的异常域收窄到具体类型（如 `OSError`、`ValueError`、`TypeError`、`RuntimeError` 等）。
- 对保留 broad catch 的边界/清理路径补齐策略语义与结构化日志上下文。
- 在本波结束时同步下调 allowlist 基线并通过门禁回归。

**Non-Goals:**
- 不修改 HTTP API 契约。
- 不修改 runtime schema/invariants。
- 不进行大规模 auth 架构重写，仅做可验证、可回滚的小步收敛。

## Decisions

### 1) Wave3 收敛顺序
1. `server/services/orchestration/engine_auth_flow_manager.py`
2. `server/engines/*/auth/runtime_handler.py`（opencode → codex → gemini/iflow）
3. `server/services/ui/ui_shell_manager.py`（仅清理可确定分支）
4. 门禁与 allowlist 基线递减

选择该顺序的原因：先处理 orchestrator/handler 主干，再处理外围路径，可最大化风险收益比并减少行为漂移。

### 2) 收窄决策表（compat-first）
- 纯 parse/convert：收窄到 `TypeError/ValueError/OverflowError`
- I/O/system 调用：收窄到 `OSError`（必要时加 `RuntimeError`）
- cleanup/finalizer：允许保留 broad catch，但必须声明 best-effort 语义，且不遮蔽主异常
- router boundary：保持 broad catch 映射兼容，但统一走结构化错误出口

### 3) 兼容护栏
- 保持既有失败码、错误消息路径、fallback 顺序。
- 禁止为“顺便优化”改变成功/失败语义。
- 每个波次变更后必须先过 AST 门禁，再过目标模块回归。

## Risks / Trade-offs

- [Risk] 过度收窄导致第三方异常穿透并改变失败路径。  
  → Mitigation: 边界层保持 broad catch + 标准化错误映射，业务层小步收窄并逐步验证。

- [Risk] auth runtime 分支复杂，局部改动可能影响 session 状态推进。  
  → Mitigation: 波次内以单文件小步改造，优先跑 auth manager/runtime handler 回归与关键 runtime 测试。

- [Risk] baseline 更新遗漏导致门禁失真。  
  → Mitigation: 把 allowlist 下调设为独立任务并与门禁测试绑定执行。

## Migration Plan

1. 以 wave3 task 顺序逐文件收窄并补注释/日志语义。  
2. 每完成一组模块即执行对应回归与门禁。  
3. 全部通过后更新 `exception_handling_allowlist.yaml` 到新低基线。  
4. 若回归出现语义偏移，按文件粒度回滚本波改动，不回滚已验证模块。  

## Open Questions

- _None._
