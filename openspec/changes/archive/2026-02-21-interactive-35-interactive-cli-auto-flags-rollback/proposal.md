## Why

在 `interactive-20-adapter-turn-protocol-and-mode-aware-patching` 中，CLI 命令构造被改为在 `interactive` 模式移除自动执行参数（Gemini/iFlow 去掉 `--yolo`，Codex 去掉 `--full-auto`/`--yolo`）。

最新实验表明该策略会影响工具执行稳定性；对当前三引擎实现，`interactive` 回合同样需要保留自动执行参数。

## What Changes

- 回滚上述“interactive 模式移除自动执行参数”的行为。
- 统一规则为：
  - Gemini / iFlow：`auto` 与 `interactive` 均包含 `--yolo`；
  - Codex：`auto` 与 `interactive` 均包含自动执行参数（`--full-auto` 或 `--yolo`）。
- 对 `interactive` 的 resume 回合应用相同规则，避免首回合与续跑回合行为不一致。
- 修改 `interactive-engine-turn-protocol` 的规格增量，反映回滚后的行为。

## Capabilities

### Modified Capabilities
- `interactive-engine-turn-protocol`

## Impact

- Affected code:
  - `server/adapters/codex_adapter.py`
  - `server/adapters/gemini_adapter.py`
  - `server/adapters/iflow_adapter.py`
- Affected tests:
  - `tests/unit/test_codex_adapter.py`
  - `tests/unit/test_gemini_adapter.py`
  - `tests/unit/test_iflow_adapter.py`
