## Context

当前三引擎命令参数策略已在 `interactive-engine-turn-protocol` 中定义，但 iFlow 仍缺少 `--thinking` 的强制默认注入约束。  
这会导致 iFlow 在不同执行路径（首回合与 resume 回合）上的参数组合不一致。

## Goals / Non-Goals

**Goals:**
- 让 iFlow 在所有执行路径默认包含 `--thinking`。
- 保持非 resume 与 resume 回合参数策略一致。
- 将该行为沉淀到主规格，避免后续回归。

**Non-Goals:**
- 不修改 Gemini/Codex 的参数策略。
- 不调整 execution mode 语义与交互协议。
- 不引入新的 runtime_options 控制开关。

## Decisions

### Decision 1: iFlow 非 resume 回合统一追加 `--thinking`
- 在 `_execute_process` 的 iFlow 非 resume 命令构造分支中，固定加入 `--thinking`。
- 保持现有 `--yolo`、`-p <prompt>` 逻辑不变，仅新增默认参数。

Rationale:
- 满足“默认所有场景启用 thinking”的产品要求。
- 变更面最小，不影响既有 mode 分支。

### Decision 2: iFlow resume 回合同样追加 `--thinking`
- 在 `build_resume_command` 中加入 `--thinking`，与首回合策略保持一致。

Rationale:
- 避免首回合与续跑回合参数漂移。
- 保障交互式多回合执行行为一致。

### Decision 3: 规格通过修改既有能力完成约束落地
- 在 `interactive-engine-turn-protocol` 的 delta spec 中，修改“Adapter CLI 命令构造” requirement。
- 明确 iFlow 在 `auto`、`interactive`、`interactive resume` 均 MUST 包含 `--thinking`。

Rationale:
- 该变更是既有能力的行为增强，不需要新增 capability。

## Risks / Trade-offs

- [Risk] 旧版本 iFlow CLI 可能不识别 `--thinking`。  
  → Mitigation: 在 adapter 单测中固定命令构造；上线前通过实际 CLI 版本回归验证。

- [Trade-off] 无条件追加会降低参数可配置性。  
  → Mitigation: 当前需求明确“默认总是加入”，后续若有需求再通过新 change 引入开关。

## Migration Plan

1. 更新 change 规格与任务清单。
2. 实现 `iflow_adapter` 命令构造调整（非 resume + resume）。
3. 更新并运行 iFlow adapter 单测。
4. 运行 `mypy server` 与变更相关回归测试。
5. verify 后进入 archive。

Rollback:
- 回滚 `iflow_adapter` 的 `--thinking` 注入变更，并恢复对应单测与规格文本。

## Open Questions

- None.
