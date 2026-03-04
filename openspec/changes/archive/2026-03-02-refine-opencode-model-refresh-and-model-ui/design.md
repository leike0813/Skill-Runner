# Design: refine-opencode-model-refresh-and-model-ui

## Summary

本次改动将 `opencode` 模型目录刷新路径统一到 `OpencodeModelCatalog.refresh(...)`，避免继续同时维护“启动异步请求刷新”和“页面手动刷新”两套逻辑。

## Decisions

### 1. Startup refresh must be awaited in `main.py`

- `OpencodeModelCatalog.start()` 只负责加载缓存/seed 与启动 scheduler
- 启动阶段是否执行一次主动刷新，由 `main.py` 决定
- 当 `OPENCODE_MODELS_STARTUP_PROBE=true` 时，`lifespan` 中显式：
  - `await opencode_model_catalog.refresh(reason="startup")`
- 若刷新失败：
  - 记录 warning
  - 保留现有缓存/seed 回退
  - 不阻断服务启动

### 2. Manual refresh uses the same canonical refresh path and HTMX partial rendering

- 新增 UI 路由：
  - `POST /ui/engines/opencode/models/refresh`
- 该路由直接：
  - `await opencode_model_catalog.refresh(reason="ui_manual_refresh")`
- 完成后直接返回模型管理页 partial，并显示成功或失败消息
- 整页模板与手动刷新响应共用同一份 panel partial，避免重复渲染逻辑

### 3. Model management UI keeps `id`, but collapses visible model labeling

- 当前列表页保留 `id` 列
- 删除 `display_name` 列
- `model` 列显示规则：
  - `opencode`: 显示 `model`
  - 其他引擎：优先显示 `display_name`，否则回退 `model`

### 4. Snapshot add form collapses `display_name` input into `model`

- 对非 `opencode` 的快照新增表单：
  - 保留 `id`
  - 将 `display_name` 输入改名为 `model`
- 提交时后端归一化为：
  - `id = id`
  - `display_name = model`
- 这样保留现有 manifest 存储结构，避免扩大回归面

## Files

- `server/engines/opencode/models/catalog_service.py`
- `server/main.py`
- `server/routers/ui.py`
- `server/assets/templates/ui/engine_models.html`
- `tests/unit/test_ui_routes.py`
- `tests/unit/test_opencode_model_catalog_startup.py`
