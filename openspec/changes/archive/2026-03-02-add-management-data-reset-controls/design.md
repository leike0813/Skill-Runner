## Context

项目已有 `scripts/reset_project_data.py`，可清理 SQLite 与落盘目录并重建必要目录。但当前仅支持命令行触发，不适合管理 UI 场景，也缺少统一的高危确认流程。新需求要求在管理 API 与管理 UI 提供等价能力，并通过强确认机制降低误操作风险。

## Goals / Non-Goals

**Goals:**
- 为管理 API 增加与清理脚本等价的数据重置能力。
- 为管理 UI 增加高危操作入口、显著危险提示、弹窗二次确认与手动输入确认文本。
- 复用同一套重置核心逻辑，避免脚本行为与 API 行为漂移。
- 保持 HTTP 业务语义、runtime schema/invariants、状态机语义不变。

**Non-Goals:**
- 不变更 run/audit 协议结构。
- 不新增外部依赖。
- 不改动非管理域页面交互。
- 不在本次变更中扩展跨节点/分布式数据清理能力。

## Decisions

### 1) 提取共享重置核心逻辑（脚本与 API 共用）
- Decision: 将 `reset_project_data.py` 内目标构建与删除/重建逻辑抽取到服务层模块（如 `server/services/platform/data_reset_service.py`），脚本与管理路由均调用该模块。
- Rationale: 避免“双实现”导致行为漂移；后续规则调整只需改一处。
- Alternative considered: API 端复制脚本逻辑。拒绝原因：维护成本高，容易出现目标路径不一致。

### 2) 管理 API 采用“确认文本 + 参数化选项 + dry-run”合同
- Decision: 新增管理端点（`/v1/management/system/reset-data`），请求体包含：
  - `confirmation`（必填，固定短语）
  - 可选开关（与脚本现有 include 选项对齐）
  - `dry_run`（默认 `false`）
- Rationale: 服务端强校验确认文本，避免前端绕过；`dry_run` 便于先预览再执行。
- Alternative considered: 仅靠前端弹窗确认。拒绝原因：缺乏服务端硬约束，不满足防误触要求。

### 3) 高危操作保持同步结果返回，阻塞逻辑放到线程池
- Decision: 路由保持请求-响应模型，返回结构化统计；文件系统删除/重建在后台线程执行（避免阻塞事件循环）。
- Rationale: 管理操作需要即时成功/失败反馈，同时避免在 async 路由中直接执行大量阻塞 I/O。
- Alternative considered: 完全异步任务队列。拒绝原因：本次范围内会引入任务状态管理复杂度。

### 4) 管理 UI 在首页新增“Danger Zone + Modal + 手动输入”
- Decision: 在 `/ui` 页面新增独立危险操作卡片，使用醒目红色样式；点击后弹窗输入固定确认文本才可提交。
- Rationale: 将高危动作与普通操作视觉隔离，减少误点击。
- Alternative considered: 原地二次点击确认。拒绝原因：风险提示不够强、可误触。

### 5) 响应模型新增专用结果类型
- Decision: 在 management models 中新增 reset 请求/响应模型，返回目标路径与统计计数。
- Rationale: 保持管理接口返回结构化、可测试、可扩展。
- Alternative considered: 返回松散 `dict[str, Any]`。拒绝原因：类型约束弱，不利于测试与长期维护。

## Risks / Trade-offs

- [Risk] 高危接口被误调用导致本地数据丢失。
  - Mitigation: 服务端确认文本硬校验 + UI 危险提示 + 手动输入确认。

- [Risk] 文件系统清理在运行中触发，影响正在进行的会话。
  - Mitigation: 返回操作提示；文档明确“仅在维护窗口执行”；必要时在实现中增加活跃运行检测告警。

- [Risk] 脚本和 API 行为未来再次偏移。
  - Mitigation: 强制复用同一服务模块，并新增测试覆盖脚本/API 结果一致性。

- [Risk] 并发重置请求冲突。
  - Mitigation: 在服务层增加进程内互斥锁，保证同一时刻仅执行一次真实重置。

## Migration Plan

1. 新增共享重置服务并迁移脚本逻辑，保持脚本 CLI 行为兼容。
2. 新增管理 API 模型与路由，接入共享服务。
3. 在 UI 首页新增 Danger Zone、弹窗与确认输入流程。
4. 补充管理路由/UI 单测（确认失败、dry-run、成功执行）。
5. 通过 `openspec status` 确认为 apply-ready 后进入实现。
6. 若回滚：保留脚本，移除管理端点与 UI 入口即可恢复旧行为。

## Open Questions

- 无。当前范围、交互方式、确认策略已锁定，可直接进入实现。
