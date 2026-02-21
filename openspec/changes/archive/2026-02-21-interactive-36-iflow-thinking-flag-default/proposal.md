## Why

当前 iFlow adapter 的 CLI 参数未将 `--thinking` 作为默认参数注入到所有执行路径。  
为保证 iFlow 在常规执行与交互续跑中的行为一致，需要将 `--thinking` 设为默认启用。

## What Changes

- 修改 iFlow adapter 的命令构造逻辑：在所有执行场景默认附加 `--thinking`。
- 覆盖场景包括：
  - 非 resume 回合（`auto` / `interactive`）
  - resume 回合（交互回复后继续执行）
- 同步更新 `interactive-engine-turn-protocol` 规格中的 iFlow 命令约束。
- 同步更新 iFlow adapter 单测断言。

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `interactive-engine-turn-protocol`: 补充 iFlow CLI 命令在所有场景必须包含 `--thinking` 的要求。

## Impact

- Affected code:
  - `server/adapters/iflow_adapter.py`
- Affected tests:
  - `tests/unit/test_iflow_adapter.py`
- Affected specs:
  - `openspec/specs/interactive-engine-turn-protocol/spec.md`
