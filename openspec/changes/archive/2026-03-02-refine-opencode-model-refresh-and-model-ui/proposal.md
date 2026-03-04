# Proposal: refine-opencode-model-refresh-and-model-ui

## Why

当前 `opencode` 模型目录在服务启动时仅异步请求刷新，不等待刷新完成，导致首批页面访问可能仍读取旧缓存或 seed 数据。与此同时，`/ui/engines/{engine}/models` 页面缺少手动刷新能力，且模型表格同时展示 `model` 与 `display_name` 两列，非 `opencode` 引擎的展示语义重复。

## What Changes

- 将 `opencode` 模型目录改为启动阶段 `await` 一次刷新
- 在 `opencode` 模型管理页增加手动刷新按钮，并通过 HTMX 局部刷新更新页面内容
- 将模型管理页展示与表单统一为单一 `model` 展示/输入语义
- 保持底层模型 API 和 manifest 存储结构兼容

## Impact

- 主要影响 `server/engines/opencode/models/catalog_service.py`
- 主要影响 `server/main.py`
- 主要影响 `/ui/engines/{engine}/models` 页面和对应 UI 路由
- 不修改公开 `/v1/engines/{engine}/models` API 结构
