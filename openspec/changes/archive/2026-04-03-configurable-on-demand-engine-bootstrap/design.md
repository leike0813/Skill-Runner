# configurable-on-demand-engine-bootstrap Design

## Bootstrap target resolution

新增统一的 engine 子集解析规则：

- 输入来源优先级：
  1. CLI `--engines`
  2. 环境变量 `SKILL_RUNNER_BOOTSTRAP_ENGINES`
  3. 默认值 `opencode,codex`
- 允许值：
  - `all`
  - `none`
  - 逗号分隔 engine 列表

解析结果统一产出：

- `requested_engines`
- `resolved_mode`：`all | none | subset`
- `skipped_engines`

该逻辑收敛在 `AgentCliManager`，避免 `agent_manager.py`、`skill_runnerctl.py`、UI/升级域各自散落解析。

## Ensure behavior

`agent_manager.py --ensure` 不再默认对 `supported_engines()` 做全量安装，而是仅对解析得到的 `requested_engines` 执行 ensure。

诊断报告扩展：

- `summary.requested_engines`
- `summary.skipped_engines`
- `summary.resolved_mode`

`summary.engines_total` 表示本次请求的目标数，而非平台支持总数。

当 `resolved_mode=none` 时：

- 仍执行 `ensure_layout()`
- 仍写 bootstrap report 与状态缓存
- 不执行任何 engine install

## Single-engine install via upgrade task

管理 UI 继续复用现有单 engine 升级按钮和升级任务通道。

当创建 `mode=single` 任务时：

- 若目标 engine 在 managed prefix 下不存在，则该任务执行 single-engine ensure/install
- 若目标 engine 已存在，则执行现有 single-engine upgrade

任务结果新增 `action` 字段，取值为：

- `install`
- `upgrade`

这样状态面板和后续 API 查询可以准确显示本次动作，不再把 install 误呈现为 upgrade。

## UI behavior

`/ui/engines` 表格不新增按钮。

现有单 engine 升级按钮根据 `engine_status_cache` 中的 `present` 动态表现：

- `present=false` -> 文案显示“安装”
- `present=true` -> 文案显示“升级”

按钮提交仍走现有 `/ui/engines/upgrades`，后端由任务域决定 action。
