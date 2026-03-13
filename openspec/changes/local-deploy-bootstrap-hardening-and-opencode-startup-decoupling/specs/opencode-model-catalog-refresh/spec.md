## MODIFIED Requirements

### Requirement: Opencode model catalog startup probe MUST NOT block API startup
系统 MUST 在服务启动阶段异步触发 `opencode` 模型目录刷新，而不是在 lifespan 中 `await` 刷新完成。

#### Scenario: startup schedules refresh without await blocking
- **WHEN** 服务启动且 `ENGINE_MODELS_CATALOG_STARTUP_PROBE=true`
- **THEN** 系统在 startup 中异步调度 `opencode models` 刷新任务
- **AND** API 启动流程不等待该刷新任务完成
- **AND** 刷新失败时保留缓存或 seed 回退且不阻断启动
