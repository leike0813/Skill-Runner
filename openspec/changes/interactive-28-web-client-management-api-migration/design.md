## Context

`interactive-27` 已将统一管理 API 作为多前端共用契约，  
但内建 Web 客户端仍有历史 UI 专用接口与 HTML partial 依赖，尚未完全对齐。

这会导致：
- 同一业务语义在 UI/API 层重复实现；
- 外部前端与内建前端行为不一致；
- 新能力（interactive + SSE）在 UI 侧接入成本升高。

## Goals

1. 内建 Web 客户端全面切换到 management API 数据源。
2. Run 页面形成对话窗口模型：状态 + 文件浏览 + SSE 输出 + pending/reply。
3. 旧 UI 数据接口进入可执行的弃用生命周期。
4. 保持 `/ui` 页面路径和页面范围不变。

## Non-Goals

1. 不新增新的 UI 功能域（范围仍是 Skill/Engine/Run）。
2. 不改变后端执行引擎与调度策略。
3. 不在本 change 强制移除全部旧接口（先完成迁移与弃用标记）。

## Prerequisite

- `interactive-25-api-sse-log-streaming` 已提供可用 SSE 事件流接口。
- `interactive-26-job-termination-api-and-frontend-control` 已提供稳定 cancel 语义。
- `interactive-27-unified-management-api-surface` 已提供统一 management API 语义。

## Design

### 1) 客户端数据层重构

将内建 Web 客户端数据访问抽象为统一 API client（可在前端脚本或后端 UI service 中实现）：
- `fetchSkills*` -> `/v1/management/skills*`
- `fetchEngines*` -> `/v1/management/engines*`
- `fetchRun*` -> `/v1/management/runs*`

要求：
- UI 模板不再直接拼接旧 UI 数据接口；
- 页面渲染只依赖统一 DTO 字段。

### 2) Run 对话窗口模型

Run 页面最小信息区块：
- 会话状态区：`status`, `pending_interaction_id`, `interaction_count`
- 实时输出区：消费 SSE（stdout/stderr/status/end）
- 交互操作区：pending 展示与 reply 提交
- 终止操作区：cancel 当前运行
- 文件浏览区：文件树 + 预览

行为：
- `status=running`：保持 SSE 连接；
- `status=waiting_user`：展示待答问题，启用回复输入；
- reply 成功后重连 SSE，继续会话；
- 终态时关闭输入并固定最终状态。

### 3) 旧 UI 数据接口弃用策略

弃用分三阶段：
1. **Deprecation 标记期**：
   - 保留接口行为；
   - 在文档与响应头（如 `Deprecation: true`）标记；
   - 提供替代 management API 路径。
2. **Compatibility 观测期**：
   - 记录旧接口调用量；
   - 验证内建 UI 不再调用旧接口。
3. **Removal 期**：
   - 对弃用接口返回 410 或移除路由（按最终发布策略）。

### 4) 向后兼容

- `/ui/*` 页面继续可访问；
- 执行 API（`/v1/jobs*`, `/v1/temp-skill-runs*`）保持兼容；
- 本 change 重点是内建客户端迁移，不破坏核心执行链路。

## Risks & Mitigations

1. **风险：UI 迁移期间字段映射缺失导致页面回归**
   - 缓解：引入 DTO 契约测试，页面关键字段快照测试。
2. **风险：弃用接口仍被第三方隐式依赖**
   - 缓解：先观测调用量，再进入 410/移除阶段。
3. **风险：Run 对话窗口状态机复杂度上升**
   - 缓解：以 `running/waiting_user/terminal` 三态驱动 UI 行为，避免隐式状态。
