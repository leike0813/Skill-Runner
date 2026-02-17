# interactive-27-unified-management-api-surface 实现记录

## 变更范围
- 新增统一管理 API 路由：
  - 新增 `server/routers/management.py`
  - 路由前缀：`/v1/management`
  - 覆盖三域接口：
    - Skills：`GET /skills`、`GET /skills/{skill_id}`
    - Engines：`GET /engines`、`GET /engines/{engine}`
    - Runs：`GET /runs`、`GET /runs/{request_id}`、`GET /runs/{request_id}/files`、`GET /runs/{request_id}/file`
    - Run 动作：`GET /runs/{request_id}/events`、`GET /runs/{request_id}/pending`、`POST /runs/{request_id}/reply`、`POST /runs/{request_id}/cancel`
- 新增管理 DTO：
  - `server/models.py` 新增 Skill/Engine/Run 的 management summary/detail 与文件响应模型
- 运行交互统计能力：
  - `server/services/run_store.py` 新增 `get_interaction_count`
- 应用入口接线：
  - `server/main.py` 将 `management.router` 挂载进 `/v1`
- 文档与迁移说明：
  - `docs/api_reference.md` 新增 management API 章节
  - `docs/dev_guide.md` 新增 Domain API / UI Adapter 分层约定与 management 端点
  - 在 legacy 执行域接口章节补“推荐迁移到 management API”注释

## 测试与校验
- 定向单测：
  - `36 passed`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m pytest tests/unit/test_management_routes.py tests/unit/test_v1_routes.py -q`
- 管理 API 联通测试：
  - `7 passed`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m pytest tests/unit/test_management_routes.py tests/integration/test_management_api.py -q`
- 全量单元测试：
  - `315 passed`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m pytest tests/unit -q`
- 类型检查：
  - `Success: no issues found in 52 source files`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m mypy server`
- OpenSpec：
  - `openspec validate interactive-27-unified-management-api-surface --type change --strict --no-interactive`
  - `openspec archive interactive-27-unified-management-api-surface -y`
  - 归档目录：`openspec/changes/archive/2026-02-16-interactive-27-unified-management-api-surface`
  - 同步 spec：
    - `openspec/specs/management-api-surface/spec.md`
    - `openspec/specs/run-observability-ui/spec.md`
    - `openspec/specs/ui-engine-management/spec.md`
    - `openspec/specs/ui-skill-browser/spec.md`
