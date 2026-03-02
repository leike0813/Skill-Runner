## Why

当前管理 UI 将高危 data reset 操作直接放在首页，信息架构过于激进；同时 reset 选项没有正确反映 `engine auth session` 日志功能的默认关闭状态。另一方面，日志策略目前仍主要依赖启动期配置，缺少一个可由 UI 查看和修改的最小运行时设置面。

## What Changes

- 将 data reset 危险操作从 `/ui` 首页迁移到新的 `/ui/settings` 页面。
- 新增 Settings 页面，提供日志设置的最小可写集与只读运行时输入展示。
- 新增管理 API，用于读取与更新运行时日志设置，并在更新后触发日志热重载。
- 新增 `data/system_settings.json` 与 bootstrap 初始化逻辑，但仅承载 UI 可见且可写的日志设置项。
- 修正 reset UI/服务能力边界：当 `engine auth session` 日志持久化关闭时，UI 完全隐藏相关清理选项，后端也会归一化忽略该开关。

## Capabilities

### New Capabilities

- `logging-persistence-controls`: 为可由 UI 管理的日志设置建立持久化、热重载与 bootstrap 初始化约束。

### Modified Capabilities

- `management-api-surface`: 新增系统设置读取/更新接口，并保持现有 reset API 兼容。
- `web-management-ui`: 新增独立 Settings 页面，迁移首页危险操作区，并要求 reset 选项反映实际能力状态。

## Impact

- Affected code:
  - `server/routers/ui.py`
  - `server/routers/management.py`
  - `server/models/management.py`
  - `server/logging_config.py`
  - `server/core_config.py`
  - `server/services/platform/data_reset_service.py`
  - `server/services/platform/system_settings_service.py`
  - `server/assets/templates/ui/index.html`
  - `server/assets/templates/ui/settings.html`
  - `tests/unit/test_management_routes.py`
  - `tests/unit/test_ui_routes.py`
  - `tests/unit/test_logging_config.py`
  - `tests/unit/test_data_reset_service.py`
  - `tests/unit/test_system_settings_service.py`
- Public API:
  - HTTP API: 新增系统设置 GET/PUT 接口；`POST /v1/management/system/reset-data` 保持兼容
  - runtime schema/invariants: no change
- Dependencies:
  - 无新增外部依赖
