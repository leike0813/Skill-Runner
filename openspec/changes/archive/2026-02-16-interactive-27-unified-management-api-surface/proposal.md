## Why

当前管理能力（Skill / Engine / Run）的接口形态仍偏向“服务内置网页 UI”消费，复用到其他前端（如 Zotero 插件内嵌页）时需要额外适配。  
在 interactive 与 SSE 能力引入后，需要统一一组稳定、前端无关的管理 API 契约，作为未来多前端形态的共同基础。

## What Changes

1. 新增一组“前端无关”的管理 API 契约，覆盖 Skill 管理、Engine 管理、Run 管理三大域。
2. 明确将现有 `/ui/*` 接口定位为“内置 UI 适配层”，不作为外部前端首选契约。
3. Run 管理 API 面向“对话窗口”体验定义数据模型：文件树浏览、日志实时事件流、pending/reply 交互动作统一收口。
4. 保持现有 UI 页面范围不变，不在本 change 新增 UI 页面，仅重构接口分层与契约。
5. 与 `interactive-25`（SSE）、`interactive-26`（Job 终止 API）及 `interactive-30`（观测测试文档）建立依赖关系与边界。

## Capabilities

### New Capabilities
- `management-api-surface`: 定义可被任意前端复用的统一管理 API 面（Skill / Engine / Run），并规范 Run 对话式管理所需的数据与动作接口。

### Modified Capabilities
- `run-observability-ui`: 将 run 可观测能力从 UI 专用语义扩展为“通用 API 优先，UI 作为适配层消费”。
- `ui-engine-management`: 明确 engine 管理信息需由通用 API 提供稳定字段，UI 仅负责渲染。
- `ui-skill-browser`: 明确 skill 浏览/管理信息需由通用 API 提供稳定字段，UI 仅负责渲染。

## Impact

- `server/routers/ui.py`
- `server/routers/jobs.py`
- `server/routers/temp_skill_runs.py`
- `server/routers/skills.py`
- `server/routers/engines.py`
- `server/services/run_observability.py`
- `docs/api_reference.md`
- `docs/dev_guide.md`
- `tests/unit/test_v1_routes.py`
- `tests/unit/test_ui_routes.py`
- `tests/integration/run_integration_tests.py`
