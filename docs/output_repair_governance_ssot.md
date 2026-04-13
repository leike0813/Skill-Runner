# Output Repair Governance SSOT

## 1. Purpose

本文档定义 output convergence / repair 的治理模型，是 phase 3B 之前的规范锚点。

它解决四件事：

- `attempt` 与 `internal_round` 的双层关系
- output convergence 的唯一执行者
- deterministic parse repair、schema repair、legacy fallback 的统一顺序
- repair 事件与审计资产的目标合同

当前实现尚未完整落地本文档；未落地部分均属于 `phase 3B target / current implementation not yet enforced`。

## 2. 双层模型

- `attempt`：外层生命周期执行单元，由 orchestrator 驱动，也是用户与当前审计最稳定的主计数。
- `internal_round`：`attempt` 内部的输出收敛轮次，只服务 output convergence，不改变 `attempt_number`。

约束：

- repair round 不得创建新的 attempt
- repair round 只属于当前 attempt 的内部历史
- legacy fallback 发生时，控制权仍先回到当前 attempt 的 lifecycle normalization，而不是直接跳出模型

## 3. 唯一执行者

唯一 repair 决策者是 orchestrator 侧的 `output convergence executor`。

职责：

- 接收 parser / adapter / result-file 等来源的 candidate
- 判断是否进入 schema repair round
- 判断 repair 是否 exhausted / skipped
- 决定何时回落到 legacy lifecycle / result-file / interactive waiting 路径

非职责：

- parser / adapter 不能独立裁定 complete / waiting
- interaction service 不能独立成为 repair 决策者
- skill patcher 不能拥有 repair ownership

## 4. 统一治理链

目标治理顺序固定为：

1. deterministic parse repair
2. schema repair rounds
3. legacy lifecycle fallback
4. legacy result-file fallback
5. legacy interactive waiting / soft-completion heuristics

说明：

- 前两步属于 output convergence executor 的主动治理区
- 后三步在当前实现中仍大量存在，因此必须纳入同一模型，但统一标记为 `legacy / current implementation only`
- `<ASK_USER_YAML>`、interactive invalid-structured-output waiting、soft completion 都只属于末端 legacy fallback 语义

## 5. 事件合同

repair 事件属于 orchestrator audit 层，分类固定为 `diagnostic`，不进入 FCMP / RASP public event surface。

预留事件类型：

- `diagnostic.output_repair.started`
- `diagnostic.output_repair.round.started`
- `diagnostic.output_repair.round.completed`
- `diagnostic.output_repair.converged`
- `diagnostic.output_repair.exhausted`
- `diagnostic.output_repair.skipped`

公共字段：

- `attempt_number`
- `internal_round_index`
- `repair_stage`
- `candidate_source`

补充字段：

- `reason`
- `skip_reason`
- `legacy_fallback_target`

## 6. 审计资产

phase 3B 的目标审计文件为：

- `.audit/output_repair.<attempt>.jsonl`

该文件的合同是：

- attempt-scoped
- append-only
- history-only
- 非 current truth

记录至少包含：

- `attempt_number`
- `internal_round_index`
- `repair_stage`
- `candidate_source`
- `executor`
- `validation_errors`
- `repair_prompt_or_summary`
- `converged`
- `legacy_fallback_target`

## 7. 当前实现与目标模型的边界

当前实现仍允许以下 legacy 路径存在：

- deterministic generic repair 直接帮助主路径成功
- result-file fallback 直接恢复 terminal output
- unresolved interactive attempts 仍可能通过 lifecycle fallback 进入 waiting，但 fallback payload 会退化为默认 pending
- interactive soft completion 在无显式 done-marker 时完成

这些行为在 phase 3A 之后仍不会被删除，但必须统一理解为：

- 它们都属于 output convergence 治理模型中的 legacy fallback
- 它们不是未来 phase 3B 的首选治理面
