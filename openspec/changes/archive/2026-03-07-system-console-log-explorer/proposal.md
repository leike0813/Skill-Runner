## Why

当前 `/ui/settings` 页面语义偏“配置项编辑”，但实际已经承载日志管理与数据重置等运维动作。  
同时，容器部署引入了 `bootstrap.log`，目前管理端无法统一查看、搜索、筛选系统日志与 bootstrap 日志，排障效率不足。

## What Changes

- 将 `/ui/settings` 页面文案语义统一为 **System Console**（路由保持不变）。
- 新增管理 API：`GET /v1/management/system/logs/query`，支持 `system|bootstrap` 两类日志源的查询、过滤与分页。
- 在 System Console 页面新增 `Log Explorer` 模块（源切换、关键词、级别、时间范围、Load more）。
- 同步更新 `docs/api_reference.md` 与 `docs/dev_guide.md` 的管理 API 文档。

## Capabilities

### New Capabilities

- `management-api-surface`: 新增系统日志查询接口，统一读取 system/bootstrap 日志。

### Modified Capabilities

- `ui-engine-management`: `/ui/settings` 语义升级为 System Console，并新增日志浏览能力。
- `logging-persistence-controls`: 在现有日志设置/重置控制之外，增加日志查询可观测面。

## Impact

- Affected code:
  - `server/services/platform/system_log_explorer_service.py`（新增）
  - `server/routers/management.py`
  - `server/models/management.py`
  - `server/models/__init__.py`
  - `server/assets/templates/ui/settings.html`
  - `server/assets/templates/ui/partials/settings_log_explorer_panel.html`（新增）
  - `server/assets/templates/ui/index.html`
  - `server/locales/*.json`
  - `docs/api_reference.md`
  - `docs/dev_guide.md`
- API impact:
  - 新增 `GET /v1/management/system/logs/query`
- Protocol impact: None.
