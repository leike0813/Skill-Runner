# opencode-model-catalog-refresh Specification

## Purpose
定义 `opencode` 模型目录的启动刷新与管理页手动刷新约束，确保页面读取基于已刷新缓存，并支持局部交互更新。
## Requirements
### Requirement: Opencode model catalog MUST await one startup refresh
系统 MUST 在服务启动阶段对 `opencode` 模型目录执行一次 awaited 刷新，而不是仅异步请求刷新。

#### Scenario: startup refresh completes before steady-state reads
- **WHEN** 服务启动且 `OPENCODE_MODELS_STARTUP_PROBE=true`
- **THEN** 系统在进入稳态页面读取前 await 一次 `opencode models` 刷新
- **AND** 若刷新失败，保留缓存或 seed 回退且不阻断启动

### Requirement: Opencode model management UI MUST support manual refresh
系统 MUST 在 `opencode` 模型管理页提供手动刷新能力，并在刷新完成后通过局部更新返回最新内容。

#### Scenario: user clicks manual refresh
- **WHEN** 用户在 `/ui/engines/opencode/models` 点击手动刷新
- **THEN** 后端 await 执行一次模型目录刷新
- **AND** 页面 MUST 通过 HTMX partial swap 更新为最新缓存内容或失败消息

### Requirement: Opencode model catalog startup probe MUST NOT block API startup
系统 MUST 在服务启动阶段异步触发 `opencode` 模型目录刷新，而不是在 lifespan 中 `await` 刷新完成。

#### Scenario: startup schedules refresh without await blocking
- **WHEN** 服务启动且 `ENGINE_MODELS_CATALOG_STARTUP_PROBE=true`
- **THEN** 系统在 startup 中异步调度 `opencode models` 刷新任务
- **AND** API 启动流程不等待该刷新任务完成
- **AND** 刷新失败时保留缓存或 seed 回退且不阻断启动

