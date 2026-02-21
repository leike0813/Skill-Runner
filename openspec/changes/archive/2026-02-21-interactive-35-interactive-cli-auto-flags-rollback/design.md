## Context

当前三引擎 adapter 的命令构造在非 resume 回合里基于 `execution_mode` 切换自动执行参数：
- `auto` 注入自动执行参数；
- `interactive` 不注入。

同时，resume 命令构造默认不注入自动执行参数。

该行为与最新实验结果冲突：interactive 回合同样需要保留自动执行参数以提高工具执行成功率与一致性。

## Goals / Non-Goals

**Goals**
- 回滚 interactive 模式对自动执行参数的移除逻辑。
- 保证同一 run 的首回合与 resume 回合在自动执行参数上保持一致。
- 通过规格增量明确“interactive 也保留自动执行参数”。

**Non-Goals**
- 不修改 `skill_patcher` 的模式语义（如 ask_user 约束文案）。
- 不调整 execution_mode 的校验逻辑。

## Decisions

### Decision 1: Gemini / iFlow 在 interactive 回合保留 `--yolo`
- 非 resume 回合：移除基于 mode 的分支，统一追加 `--yolo`。
- resume 回合：`build_resume_command` 也追加 `--yolo`。

### Decision 2: Codex 在 interactive 回合保留自动执行参数
- 非 resume 回合：无条件注入自动执行参数。
- resume 回合：同样注入自动执行参数。
- 自动执行参数选择逻辑保持不变：默认 `--full-auto`，`LANDLOCK_ENABLED=0` 时回退 `--yolo`。

### Decision 3: 规格增量仅修改 CLI 命令构造条款
- 在 `interactive-engine-turn-protocol` 的增量规格中，将 interactive 与 interactive-resume 的“不得包含自动参数”改为“必须包含自动参数”。

## Risks / Trade-offs

- 某些 CLI 版本若对 resume + 自动执行参数兼容性较差，可能出现参数解析差异。
  - Mitigation: 通过 adapter 单测固定命令构造输出，并在集成验证中观测真实 CLI 行为。
