# interactive-28-web-client-management-api-migration 实现记录

## 变更范围
- 内建 Web 客户端数据面统一到 management API：
  - `server/routers/ui.py` 新增/完善 `ui/management/*` 数据适配端点。
  - Skill/Engine/Run 页面模板数据源切换到 management API 语义。
- Run 详情页对话窗口模型落地：
  - `server/assets/templates/ui/run_detail.html` 使用 management run 状态、SSE 事件流、pending/reply、cancel、文件预览端点。
- 旧 UI 数据接口弃用策略完善：
  - `server/routers/ui.py` 统一下发 `Deprecation/Sunset/Link` 响应头。
  - 支持 `SKILL_RUNNER_UI_LEGACY_API_MODE=warn|gone`（`gone` 返回 410）。
  - 新增旧接口调用告警日志，便于兼容期观测。
- 兼容性修复：
  - `server/routers/ui.py` 增加 payload 序列化兼容（pydantic/dict/SimpleNamespace）。
  - 修复 legacy `Link` 响应头默认文档锚点非 ASCII 导致的 `latin-1` 编码异常。
- 文档：
  - `docs/api_reference.md` 补充 management API 推荐入口与弃用窗口说明，新增 `management-api-recommended` 锚点。
  - `docs/dev_guide.md` 记录 UI Adapter 与 management API 分层及 `warn/gone` 策略。
- 测试：
  - `tests/unit/test_ui_routes.py` 对齐 management mock 与 run detail 动态脚本断言。
  - `tests/integration/test_ui_management_pages.py` 对齐 run detail 动态脚本断言。

## 测试与校验
- 目标回归（UI management 迁移相关）：
  - `24 passed`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m pytest tests/unit/test_ui_routes.py tests/integration/test_ui_management_pages.py -q`
- 全量单元测试：
  - `320 passed`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m pytest tests/unit -q`
- 类型检查：
  - `Success: no issues found in 52 source files`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m mypy server`
- OpenSpec：
  - `openspec validate interactive-28-web-client-management-api-migration --type change --strict`
  - `openspec archive interactive-28-web-client-management-api-migration -y`
  - 归档目录：`openspec/changes/archive/2026-02-16-interactive-28-web-client-management-api-migration`
  - 同步 spec：
    - `openspec/specs/run-observability-ui/spec.md`
    - `openspec/specs/ui-engine-management/spec.md`
    - `openspec/specs/ui-skill-browser/spec.md`
    - `openspec/specs/web-client-management-api-adapter/spec.md`
    - `openspec/specs/web-management-ui/spec.md`
