## Context

运行时 parser 会把 engine-specific 规则命中标为 `high`，把 common fallback 命中标为 `low`。当前 adapter 在进程非零退出后，只要 `auth_signal.required=true` 就会把 `failure_reason` 设为 `AUTH_REQUIRED`，没有检查 `confidence`。这与现有规格“low 仅做审计，不得强制进入 waiting_auth 或 AUTH_REQUIRED”不一致。

## Goals / Non-Goals

**Goals:**
- 让 `AUTH_REQUIRED` 成为高置信度鉴权信号的专属失败分类。
- 保留 low fallback 的审计与诊断价值，不丢失 `AUTH_SIGNAL_MATCHED_LOW`。
- 让 `.audit/meta.*`、`result.json`、FCMP terminal 对同一次失败保持一致。

**Non-Goals:**
- 不调整 common fallback 规则本身的命中范围。
- 不引入新的 auth confidence 等级或命名变更。
- 不改变真实高置信度鉴权场景进入 `waiting_auth` 的现有路径。

## Decisions

### 1. 用统一 helper 判定“高置信度 auth required”
在 `server/runtime/auth_detection/signal.py` 增加针对 `RuntimeAuthSignal` 的 helper，并让 adapter 与 lifecycle 共用，避免两处分别手写 `required + confidence == high` 判断后再次漂移。

### 2. adapter 先修正原始 `failure_reason`
`base_execution_adapter` 是错误归因的第一落点。这里必须收紧：普通非零退出仅在 `auth_signal` 为 high 时才产出 `AUTH_REQUIRED`；idle early-exit 保持原样，因为它本来就只会被 high signal arm。

### 3. lifecycle 再做防御性清洗
即便 adapter 未来再次漂移，`run_job_lifecycle_service` 也不应盲信裸 `failure_reason="AUTH_REQUIRED"`。lifecycle 会基于 `auth_signal_snapshot` 再次确认：若不是 high signal，则清洗掉 `process_failure_reason`，并阻止 terminal error/FCMP 被翻译成 auth-required。

## Risks / Trade-offs

- [Risk] 某些测试或手写 adapter 仅返回 `failure_reason="AUTH_REQUIRED"` 而不带 `auth_signal_snapshot`。  
  → Mitigation: 更新这些测试桩，让真实高置信度场景显式提供 `auth_signal_snapshot`。

- [Risk] 低置信度样本仍会在审计里显示 `auth_required/low`，前端可能误解。  
  → Mitigation: 保持 terminal/result 不再翻译成 `AUTH_REQUIRED`，将 low 信号限定为诊断证据。

- [Risk] 后续如果 fallback 规则噪声继续扩大，本修复不能降低命中数量。  
  → Mitigation: 本 change 只修终态归因；规则精度优化另开 change 处理。
