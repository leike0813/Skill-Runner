## Why

`server/models.py` 当前约 941 行，混合了运行状态枚举、执行请求响应、引擎管理、交互协议、管理端视图、运行时事件等多类模型，维护和变更评审成本高。  
在近期多波变更后，继续沿用单文件模型定义会放大冲突面与回归风险，需要将模型按领域拆分并保留兼容导出。

## What Changes

- 将 `server/models.py` 拆分为多个按领域组织的模型模块（run/skill/engine/interaction/management/runtime_event/common）。
- 将 `server/models.py` 收敛为聚合导出层（façade），继续支持既有 `from server.models import ...` 导入方式。
- 保持 Pydantic 模型名、字段定义、默认值与 Enum 字面量不变。
- 保持对外 HTTP API、runtime schema/invariants 行为不变。
- 增加结构守卫测试，防止 `models.py` 再次回归为巨型实现文件。

## Capabilities

### New Capabilities
- `models-module-boundary`: 将集中式模型定义拆分为领域模块并保留兼容聚合导出，降低耦合与维护成本。

### Modified Capabilities
- `runtime-event-command-schema`: 明确重构不改变 runtime 事件/命令合同语义，仅允许实现位置变化。
- `management-api-surface`: 明确管理 API 响应模型重构不改变字段契约与语义。
- `interactive-job-api`: 明确交互请求/响应模型重构不改变对外字段语义。

## Impact

- Affected code:
  - `server/models.py`（从实现文件收敛为聚合层）
  - `server/models_*.py`（新增，承载分域模型定义）
  - `server/routers/*`, `server/services/*`, `server/runtime/*`, `server/engines/*`（仅在必要处调整导入来源或类型引用）
- Affected tests:
  - `tests/unit/test_runtime_event_protocol.py`
  - `tests/unit/test_management_routes.py`
  - `tests/unit/test_jobs_interaction_routes.py`
  - 新增结构守卫测试（例如 `tests/unit/test_models_module_structure.py`）
- Public API:
  - HTTP API: 无变化
  - Runtime schema/invariants: 无变化
  - Internal imports: 默认保持 `from server.models import ...` 兼容
