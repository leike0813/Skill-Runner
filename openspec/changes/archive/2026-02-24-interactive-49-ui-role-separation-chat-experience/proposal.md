## Why

当前 UI 同时承担“运维审计”和“终端用户对话”两类职责，导致：

1. 管理 UI 与 E2E UI 展示重复且边界不清晰。
2. E2E 对话页混入技术噪音（stderr/diagnostic/relation/raw_ref）。
3. Ask User YAML 被错误展示为聊天正文，未转为用户可操作提示。
4. 审计协议文件存在按最新回合覆盖，重进页面无法回看完整历史。
5. 仍在写入旧 `logs/` 与 `raw/` 通道，且 FS diff 误计入内部目录噪音。

需要新增独立变更，明确职责分离并修复 E2E 对话语义。

## Dependencies

- 依赖 `2026-02-24-interactive-45-fcmp-single-stream-event-architecture` 的 FCMP 单流消费语义。
- 依赖 `2026-02-24-interactive-46-event-command-schema-contract` 的事件合同化约束。
- 依赖 `2026-02-24-interactive-47-session-invariants-property-model-tests` 的状态/事件一致性约束。

## What Changes

1. 管理 UI 移除交互回复入口，定位为观测/审计/排障视图。
2. 新增管理 API：`GET /v1/management/runs/{request_id}/protocol/history`。
3. E2E 观察页重构为终端用户对话视图（左右气泡、快捷键发送、提示卡）。
4. Ask User YAML 从聊天气泡剥离，转为提示卡，并与 `user.input.required` 去重。
5. 新增 E2E 内部 API：`GET /api/runs/{request_id}/final-summary`，用于终态产物摘要气泡。
6. 协议审计改为按 `attempt` 分片落盘；管理页支持按轮次翻页查看。
7. 下线 E2E Replay 路由与入口；`/runs` 页面改以后端 run 数据为主。
8. 新 run 不再创建/写入旧 `run_dir/logs` 与 `run_dir/raw`。
9. FS diff 忽略规则统一到 server + harness：`.audit/`、`interactions/`、`.codex/`、`.gemini/`、`.iflow/`。
10. `chat_event.seq` 语义收敛为跨 attempt 全局单调递增（SSE/history 消费侧），attempt 本地序号保留在 `meta.local_seq`。
10.1 `fcmp_events.{attempt}.jsonl` 落盘文件中的 `seq` 同步改为全局递增，不再按 attempt 重置。
11. FCMP 去重：`assistant.message.final` 保留问询正文，`user.input.required` 仅保留控制语义，避免同文双消息。
12. `interaction.reply.accepted` 增加 `response_preview`，用于重进页面回放用户气泡。
12.1 续跑顺序收敛：`interaction.reply.accepted` 必须先于该 attempt 的 `assistant.message.final`。
13. orchestrator 事件增加 `seq`；历史旧数据在读侧回填，不做离线迁移。
14. E2E Result 页面下线，文件树能力并入 Observation 页面。
15. E2E 终态展示收敛：隐藏 completion 文本气泡，仅展示最终 summary；原始 `__SKILL_DONE__` 终态 JSON 不重复渲染。

## Capabilities

### Modified
- `run-observability-ui`
- `builtin-e2e-example-client`
- `management-api-surface`

## Impact

- 服务端：`server/services/run_observability.py`, `server/routers/management.py`
- 执行链：`server/services/job_orchestrator.py`, `server/adapters/base.py`, `server/services/workspace_manager.py`
- 管理 UI：`server/assets/templates/ui/run_detail.html`
- E2E 客户端：`e2e_client/backend.py`, `e2e_client/routes.py`, `e2e_client/templates/run_observe.html`
- Harness：`agent_harness/storage.py`
- 测试：管理路由、管理 UI、E2E 集成与语义测试
