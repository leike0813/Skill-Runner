## Why

当前内置 `/ui/runs/{request_id}` 页面虽然已接入 management API 的 pending/reply/events 能力，但整体仍是“日志观测页”结构，和交互式对话窗口体验不一致。随着 interactive 流程成为主路径，需要将 Run 观测页升级为更稳定、更易用的对话式布局，降低长内容场景下的阅读与操作成本。

## What Changes

- 将 Run 详情页调整为“文件区 + 对话区 + 错误区”的稳定布局，优先保障交互回复流程可见性与可操作性。
- 文件树与文件预览区域增加最大高度约束，超出内容走内部滚动，避免页面整体被无限拉长。
- 对话区改造为对话框式主视图：
  - 主窗口展示 Agent 输出（当前基于 stdout 事件流）。
  - 底部固定用户输入框，用于提交 interaction reply。
- stderr 从主对话区拆分为独立窗口（独立滚动与展示），避免与主对话内容混杂。
- 页面行为保持对现有 management API 契约兼容（不新增后端协议）：
  - 继续使用 `/v1/management/runs/{request_id}`、`/pending`、`/reply`、`/events`、`/cancel`。
- 同步更新 UI 与 API 文档中的 Run 页面交互说明与布局语义。

## Capabilities

### New Capabilities
- 无

### Modified Capabilities
- `run-observability-ui`: 将 Run 详情页交互体验从日志导向升级为对话导向，并新增文件区滚动约束与 stderr 独立展示要求。
- `web-management-ui`: 调整内建 UI Run 观测子页面布局规范，确保长内容场景下页面高度与交互区域稳定可用。

## Impact

- 前端模板与样式：
  - `server/assets/templates/ui/run_detail.html`
  - `server/assets/templates/ui/partials/file_preview.html`（如需滚动容器语义对齐）
- UI 路由（仅在需要传递额外展示字段时）：
  - `server/routers/ui.py`
- 文档：
  - `docs/api_reference.md`
  - `docs/dev_guide.md`
- 测试（UI 页面与交互行为回归）：
  - `tests/unit/test_ui_routes.py`
  - `tests/integration/test_ui_management_pages.py`
