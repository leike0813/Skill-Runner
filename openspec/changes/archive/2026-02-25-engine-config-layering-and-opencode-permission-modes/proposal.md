## Why

当前各引擎的运行时配置组装缺少统一的 `engine_default` 兜底层，模型未在 skill/runtime 指定时会落到 CLI 历史状态，导致执行行为不稳定。  
同时 `opencode` 尚未接入 enforce 层，且 auto/interactive 两种执行模式在项目级权限策略上缺少显式分流约束。

## What Changes

- 为 `opencode` 运行时配置组装增加 enforce 层（`server/assets/configs/opencode/enforced.json`），纳入与其他引擎一致的“强制覆盖”语义。
- 为 `codex/gemini/iflow/opencode` 增加 `engine_default` 层（优先级最低），用于补齐模型与基础运行配置缺口。
- 统一引擎配置组装顺序为：`engine_default -> skill defaults -> runtime overrides -> enforced`。
- 对 `opencode` 增加模式化权限注入：
  - auto 模式：追加 `"permission.question":"deny"`
  - interactive 模式：追加 `"permission.question":"allow"`
- 完善引擎配置组装相关文档，明确 bootstrap / engine_default / skill / runtime / enforced 的职责边界与优先级。

## Capabilities

### New Capabilities

- `engine-runtime-config-layering`: 定义多引擎统一配置组装分层（含 engine_default 与 opencode 模式权限注入）。

### Modified Capabilities

- `engine-adapter-runtime-contract`: 增补 opencode enforce 层与模式化权限注入的运行时约束。
- `runtime-environment-parity`: 增补 engine_default 配置资产与各层级职责映射，保证本地/容器环境一致行为。

## Impact

- Affected code:
  - `server/adapters/codex_adapter.py`
  - `server/adapters/gemini_adapter.py`
  - `server/adapters/iflow_adapter.py`
  - `server/adapters/opencode_adapter.py`
  - `server/services/codex_config_manager.py`
  - `server/services/config_generator.py`
  - `server/services/cache_key_builder.py`
  - `server/services/job_orchestrator.py` / `agent_harness/storage.py`（若配置文件路径或忽略策略变化）
- Affected assets:
  - `server/assets/configs/<engine>/default.*`
  - `server/assets/configs/opencode/enforced.json`
- Affected docs:
  - engine 配置组装与执行流程相关文档（core components / execution flow / containerization / dev guide）
- Potential compatibility impact:
  - 当 skill/runtime 未显式指定模型时，将优先使用 engine_default（替代依赖 CLI 历史状态）。
