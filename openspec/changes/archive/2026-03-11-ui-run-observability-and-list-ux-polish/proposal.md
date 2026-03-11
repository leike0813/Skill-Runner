## Why

Run 观测与列表页在管理 UI/E2E 客户端存在一批交互与可用性缺口：
- Bundle 下载能力在两端不一致，且 debug 包下载入口不清晰。
- Run 列表在数据量增长后缺少分页，返回列表时无法保持原分页上下文。
- Run 详情缺少 model 显示、文件树刷新时机不稳定、时间展示未按浏览器时区统一。
- 文件预览与时间线在可读性细节上仍有明显缺陷（JSON 灰底、行号、attempt 视觉分隔、气泡换行边界等）。
- OpenCode 模型刷新链路在鉴权后未自动触发，手动刷新也缺少提交中状态反馈。

## What Changes

- 新增独立 debug bundle 下载路由（不使用 query 参数分支），并在管理 UI 与 E2E 统一为两个并列下载按钮。
- 管理 API run 列表引入分页参数（默认 20/页）与分页元数据；管理 UI/E2E 列表接入分页并保持返回页上下文。
- run 列表和 run 详情状态模型补充 `model` 字段；E2E run 观测顶部展示 engine+model。
- 管理 UI run 详情文件树改为动态刷新：attempt 变化刷新、终态再刷新。
- 文件预览支持行号并修复 JSON 灰底；对话气泡修复边界换行。
- Timeline 增加 attempt 视觉分段（分隔线 + 浅色循环背景）。
- OpenCode 鉴权成功后触发模型目录刷新；手动刷新按钮在刷新期间禁用并显示提示。
- 时区展示统一到前端浏览器本地时区渲染。

## Capabilities

### Added Capabilities

- `interactive-job-api`: 新增 `GET /v1/jobs/{request_id}/bundle/debug`。

### Modified Capabilities

- `management-api-surface`: `GET /v1/management/runs` 支持分页参数并返回分页元数据。
- `ui-engine-management`: run 详情下载动作、模型展示、时间线分隔、文件树刷新与按钮可用态收敛。
- `builtin-e2e-example-client`: run 列表分页与 run 观测下载/元信息展示增强。

## Impact

- Affected code:
  - `server/routers/jobs.py`
  - `server/runtime/observability/run_read_facade.py`
  - `server/routers/management.py`
  - `server/services/orchestration/run_store.py`
  - `server/runtime/observability/run_observability.py`
  - `server/models/management.py`
  - `server/models/run.py`
  - `server/routers/ui.py`
  - `server/services/platform/file_preview_renderer.py`
  - `server/assets/templates/ui/runs.html`
  - `server/assets/templates/ui/partials/runs_table.html`
  - `server/assets/templates/ui/run_detail.html`
  - `server/assets/templates/ui/partials/file_preview.html`
  - `server/assets/templates/ui/partials/engine_models_panel.html`
  - `e2e_client/backend.py`
  - `e2e_client/routes.py`
  - `e2e_client/templates/runs.html`
  - `e2e_client/templates/run_observe.html`
  - `e2e_client/templates/partials/file_preview.html`
  - `server/locales/*.json`
  - `docs/api_reference.md`
- API impact:
  - Added `GET /v1/jobs/{request_id}/bundle/debug`
  - Added E2E proxy `GET /api/runs/{request_id}/bundle/debug/download`
  - Modified `GET /v1/management/runs` (pagination parameters + metadata)
- Protocol impact: None.
