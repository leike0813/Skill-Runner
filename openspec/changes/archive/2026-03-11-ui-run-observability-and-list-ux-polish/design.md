## Context

本次为 UI/管理接口层改进，不改 run 状态机与 FCMP/RASP 协议语义。  
核心目标是把“下载、分页、可读性、刷新时机、时区展示”收敛到稳定可预测的行为，并保持管理 UI 与 E2E 客户端一致。

## Goals / Non-Goals

**Goals**
- Bundle 下载采用两个独立入口（normal/debug）并在两端并列展示。
- Run 列表分页固定默认 20/页，详情返回列表时保持原分页上下文。
- run 详情/观测页补齐 model 信息与按钮状态可用性约束。
- 统一本地时区展示，修复文件预览与气泡文本的可读性细节。

**Non-Goals**
- 不新增 run 领域状态，不改状态迁移规则。
- 不新增 FCMP/RASP 事件类型。
- 不引入前端实时推送新通道（仍沿用现有轮询/SSE）。

## Decisions

### 1) Bundle 下载路由拆分为显式双接口

- 保留 `GET /v1/jobs/{request_id}/bundle`（normal）。
- 新增 `GET /v1/jobs/{request_id}/bundle/debug`（debug）。
- E2E proxy 同步拆分为两个 download 入口，不使用 `?debug=`。

### 2) Run 列表分页约束

- `GET /v1/management/runs` 新增 `page`、`page_size` 参数。
- 默认值：`page=1`、`page_size=20`；上限在服务端做保护。
- 返回结构补充 `total/page/page_size/total_pages`。
- 两端列表页都携带分页参数进入详情，并在返回时恢复。

### 3) 按钮可用态与刷新策略

- `Download Bundle`、`Download Debug Bundle` 仅 `status=succeeded` 可用。
- `Rebuild Protocol` 在非 terminal (`succeeded|failed|canceled`) 时禁用。
- 管理 UI run 文件树：attempt 变化刷新一次，terminal 再刷新一次。
- OpenCode 鉴权成功后触发模型缓存刷新；手动刷新提交期间按钮禁用并显示“刷新中...”。

### 4) 展示一致性

- run 列表新增 model 列；run 详情/观测顶部显示 engine + model。
- 时间统一由前端 `toLocaleString` 渲染（后端继续输出 UTC/ISO）。
- 文件预览高亮启用行号，去除 JSON 灰底。
- Timeline 增加 attempt 分隔线与浅色循环背景。
- 对话气泡文本强制在气泡边界内换行（`overflow-wrap:anywhere`）。

## File Changes

- **新增/修改（规格）**
  - `openspec/changes/ui-run-observability-and-list-ux-polish/specs/interactive-job-api/spec.md`
  - `openspec/changes/ui-run-observability-and-list-ux-polish/specs/management-api-surface/spec.md`
  - `openspec/changes/ui-run-observability-and-list-ux-polish/specs/ui-engine-management/spec.md`
  - `openspec/changes/ui-run-observability-and-list-ux-polish/specs/builtin-e2e-example-client/spec.md`
- **修改（实现）**
  - `server/routers/jobs.py`
  - `server/runtime/observability/run_read_facade.py`
  - `server/routers/management.py`
  - `server/services/orchestration/run_store.py`
  - `server/runtime/observability/run_observability.py`
  - `server/models/management.py`
  - `server/models/run.py`
  - `server/routers/ui.py`
  - `server/services/platform/file_preview_renderer.py`
  - `server/assets/templates/ui/*.html`
  - `server/assets/templates/ui/partials/*.html`
  - `e2e_client/backend.py`
  - `e2e_client/routes.py`
  - `e2e_client/templates/*.html`
  - `e2e_client/templates/partials/*.html`
  - `server/locales/*.json`
  - `docs/api_reference.md`

## Risks / Trade-offs

- [Risk] 分页改造会影响旧前端调用。
  - Mitigation: 参数与响应保持向后兼容，`page/page_size` 提供默认值。
- [Risk] 按钮禁用策略可能与用户预期冲突（例如失败态下载需求）。
  - Mitigation: 明确按产品决策仅成功态开放下载。
- [Risk] 本地时区展示导致截图对比不稳定。
  - Mitigation: 测试仅校验语义与 class，不做绝对时间字符串匹配。

## Validation

- 两端 run 详情均出现并列的 Bundle/Debug Bundle 下载按钮，且样式一致。
- run 列表可分页，进入详情再返回不丢失原分页。
- 管理 UI run 详情在 attempt 切换与终态时文件树能刷新。
- OpenCode 鉴权成功后可触发模型刷新，手动刷新有“刷新中”状态。
- 预览行号与 JSON 背景修复可见；时间显示为浏览器本地时区。
