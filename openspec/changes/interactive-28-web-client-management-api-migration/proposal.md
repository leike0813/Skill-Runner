## Why

在 `interactive-27` 定义统一管理 API 后，内建 Web 客户端仍部分依赖旧的 UI 专用数据接口，导致接口语义分裂且不利于外部前端复用。  
需要将内建 Web 客户端完整迁移到统一接口，并把旧 UI 数据接口纳入弃用路径，形成单一 API 真相源。

## What Changes

1. 内建 Web 客户端（Skill / Engine / Run 页面）全面改为消费 `/v1/management/*`。
2. Run 管理页改为“对话窗口式”交互：
   - 文件浏览与预览；
   - 实时日志（SSE）；
   - `waiting_user` 下的 pending/reply 交互。
   - 用户主动终止当前 Job（cancel）。
3. 旧 UI 数据接口进入弃用流程：
   - 标记 deprecated；
   - 提供迁移映射；
   - 在约定窗口后移除或返回 410（**BREAKING**，仅对仍依赖旧接口的客户端）。
4. 保留 `/ui/*` 页面作为内建客户端入口，但其数据层统一走 management API。

## Capabilities

### New Capabilities
- `web-client-management-api-adapter`: 定义内建 Web 客户端如何统一消费 management API（含 Run 对话窗口交互模型）。

### Modified Capabilities
- `web-management-ui`: UI 页面数据来源切换到 management API，并定义旧 UI 数据接口弃用行为。
- `run-observability-ui`: Run 页面从 tail 轮询模型升级为以 management + SSE 事件流为核心的对话式观测模型。
- `ui-engine-management`: Engine 页面字段来源统一到 management API，移除 UI 私有拼装依赖。
- `ui-skill-browser`: Skill 页面字段来源统一到 management API，移除 UI 私有数据依赖。

## Impact

- `server/routers/ui.py`
- `server/assets/templates/ui/*`
- `server/assets/static/*`（如有前端脚本）
- `server/routers/*`（旧 UI 数据接口弃用标注与迁移提示）
- `docs/api_reference.md`
- `docs/dev_guide.md`
- `tests/unit/test_ui_routes.py`
- `tests/unit/test_v1_routes.py`
- `tests/integration/*`（UI/API 兼容与弃用行为）
