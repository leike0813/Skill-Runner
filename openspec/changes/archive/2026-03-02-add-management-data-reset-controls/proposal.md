## Why

当前项目已有 `scripts/reset_project_data.py` 可执行全量数据重置，但只能通过命令行触发，且缺少面向管理 UI 的受控入口。为了让运维操作可用且可控，需要提供与脚本等价的管理接口，并通过高危确认流程降低误触发风险。

## What Changes

- 新增管理 API 高危操作：提供与 `reset_project_data.py` 等价的数据重置能力。
- 新增强确认机制：调用方必须提交固定确认文本后才允许执行重置。
- 在管理 UI 新增“危险操作”区域与显著样式按钮，点击后弹出确认窗口并要求手动输入确认信息。
- 重置结果返回结构化统计（删除/缺失/重建计数与目标路径），便于前端反馈与排障。
- 明确操作边界：保持 HTTP API 既有业务接口、runtime schema/invariants、状态机语义不变。

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `management-api-surface`: 新增受确认保护的数据重置接口与响应语义，要求显式确认后才可触发高危清理。
- `web-management-ui`: 新增高危按钮与二次确认弹窗，要求用户手动输入确认文本后执行重置。

## Impact

- Affected code:
  - `server/routers/management.py`
  - `server/routers/ui.py`
  - `server/models/management.py`
  - `server/assets/templates/ui/index.html`
  - `server/assets/templates/ui/partials/*`（如新增确认弹窗/结果片段）
  - `scripts/reset_project_data.py`（复用逻辑或对齐策略）
  - `tests/unit/test_management_routes.py`
  - `tests/unit/test_ui_routes.py`
- Public API:
  - HTTP API: 新增管理高危操作端点（非 breaking）
  - runtime schema/invariants: no change
- Dependencies:
  - 无新增外部依赖
