# 本轮改动全量详细说明（2026-02-16）

## 1. 轮次范围与总览
- 轮次主题：Interactive 能力体系从 API 合同到恢复对账的端到端落地。
- 变更来源：已归档 OpenSpec changes（`interactive-00` 至 `interactive-31` 的本轮序列）。
- 交付形态：
  - 代码实现（models/services/routers/adapters/ui/tests）
  - OpenSpec 变更验证与归档
  - 文档同步（`docs/api_reference.md`、`docs/dev_guide.md`）
  - 每个 change 的实现记录（`artifacts/interactive-*.md`）

## 2. 本轮归档清单（按执行顺序）
1. `interactive-00-api-mode-and-interaction-contract`
2. `interactive-01-skill-execution-mode-declaration-and-gating`
3. `interactive-05-engine-session-resume-compatibility`
4. `interactive-10-orchestrator-waiting-user-and-slot-release`
5. `interactive-11-session-timeout-unification-and-consumer-refactor`
6. `interactive-20-adapter-turn-protocol-and-mode-aware-patching`
7. `interactive-25-api-sse-log-streaming`
8. `interactive-26-job-termination-api-and-frontend-control`
9. `interactive-27-unified-management-api-surface`
10. `interactive-28-web-client-management-api-migration`
11. `interactive-29-decision-policy-and-auto-continue-switch`
12. `interactive-30-observability-tests-and-doc-sync`
13. `interactive-31-run-restart-recovery-and-orphan-reconciliation`

归档目录统一位于：
- `openspec/changes/archive/2026-02-16-interactive-*/`

## 3. 关键能力演进（跨 change 汇总）
- 交互执行模式建立：
  - 引入 `runtime_options.execution_mode`（`auto|interactive`）。
  - Skill 声明 `execution_modes` 并在 Jobs/TempRun 提交流程强制准入。
- 交互 API 合同建立：
  - `pending/reply` 读写闭环、幂等重放与冲突语义。
  - `waiting_user` 成为非终态。
- 会话恢复能力建立：
  - 按引擎抽取/持久化 session handle（Codex/Gemini/iFlow）。
  - `resumable` 与 `sticky_process` 双路径。
- 生命周期与并发槽位治理：
  - `waiting_user` 下分档位释放/持有 slot。
  - sticky watchdog 超时失败收敛。
- 超时配置统一：
  - `session_timeout_sec` 统一键 + 历史键兼容。
- 适配器回合协议统一：
  - `final/ask_user/error` 三态输出协议。
- 可观测性增强：
  - SSE 增量日志流（支持 offset 重连）。
  - `pending_interaction_id`、`interaction_count`、`auto_decision_count`、恢复字段统一外显。
- 取消能力完善：
  - jobs/temp-skill-runs 统一 `cancel` 接口与 `canceled` 语义。
- 管理 API 与 UI 迁移：
  - `/v1/management/*` 统一管理契约。
  - 内建 UI 数据面迁移到 management API 语义。
- 决策策略扩展：
  - strict 开关 `interactive_require_user_reply` 与自动推进策略矩阵。
- 重启恢复与孤儿对账：
  - 启动期 reconciliation、失败收敛、孤儿清理幂等、恢复字段暴露。

## 4. 分 change 详细说明

### 4.1 interactive-00：API 模式与交互合同
- 目标：
  - 引入执行模式与交互基础 API。
  - interactive 模式与缓存链路解耦。
- 实现重点：
  - `RunStatus` 增加 `waiting_user`，新增交互请求/响应模型。
  - 新增接口：
    - `GET /v1/jobs/{request_id}/interaction/pending`
    - `POST /v1/jobs/{request_id}/interaction/reply`
  - `reply` 支持 `idempotency_key`。
- 验证结果：
  - unit：`241 passed`
  - mypy：`Success (50 files)`

### 4.2 interactive-01：Skill 执行模式声明与准入
- 目标：
  - 让 skill 显式声明允许执行模式，并在提交链路强校验。
- 实现重点：
  - `SkillManifest.execution_modes` 落地。
  - 包校验与提交流程强制 `execution_mode` 准入。
  - 不支持模式返回 `SKILL_EXECUTION_MODE_UNSUPPORTED`。
- 验证结果：
  - unit：`245 passed`
  - mypy：`Success (50 files)`

### 4.3 interactive-05：引擎会话恢复兼容
- 目标：
  - 建立跨引擎恢复句柄能力与 interactive profile。
- 实现重点：
  - 新增 `EngineSessionHandle`/`EngineInteractiveProfile`/`InteractiveErrorCode`。
  - 新增运行时持久层 `request_interactive_runtime`。
  - 三引擎 handle 提取与 resume 参数接入。
- 验证结果：
  - 相关单测：`49 passed`
  - 全量 unit：`262 passed`
  - mypy：`Success (50 files)`

### 4.4 interactive-10：waiting_user 生命周期与槽位释放
- 目标：
  - 明确 waiting 阶段的并发槽位策略与 sticky watchdog。
- 实现重点：
  - `resumable` waiting 释放 slot，reply 前重占用。
  - `sticky_process` waiting 持有 slot，reply 直接续跑。
  - 增加 interaction history 持久化与镜像文件。
- 验证结果：
  - 相关单测：`42 passed`
  - 全量 unit：`267 passed`
  - mypy：`Success (50 files)`

### 4.5 interactive-11：会话超时统一与消费者重构
- 目标：
  - 用单一超时键覆盖 interactive 链路，兼容历史配置。
- 实现重点：
  - 新增 `session_timeout` 统一解析服务。
  - `session_timeout_sec` 成为统一入口。
  - `effective_session_timeout_sec` 进入持久层与可观测输出。
- 验证结果：
  - 相关单测：`73 passed`
  - 全量 unit：`275 passed`
  - mypy：`Success (51 files)`

### 4.6 interactive-20：Adapter 回合协议与 mode-aware patch
- 目标：
  - 统一引擎输出协议，确保 ask_user 契约稳定。
- 实现重点：
  - 新增 `AdapterTurnResult` 协议（`final/ask_user/error`）。
  - 三引擎 `_parse_output` 归一化。
  - patch 链拆分为 `artifact_patch -> mode_patch`。
- 验证结果：
  - 相关单测：`54 passed`
  - 全量 unit：`289 passed`
  - mypy：`Success (51 files)`

### 4.7 interactive-25：SSE 日志流
- 目标：
  - 提供可重连的增量日志消费通道。
- 实现重点：
  - 新增 `jobs/temp-skill-runs` 的 `/events`。
  - 事件：`snapshot/stdout/stderr/status/heartbeat/end`。
  - 支持 `stdout_from/stderr_from` offset 重连。
- 验证结果：
  - 相关单测：`41 passed`
  - 全量 unit：`296 passed`
  - mypy：`Success (51 files)`

### 4.8 interactive-26：任务终止 API 与前端控制
- 目标：
  - 统一取消能力与状态语义。
- 实现重点：
  - 新增 `POST /v1/jobs/{request_id}/cancel` 与 temp 对应接口。
  - 引入 `cancel_requested` 持久化与运行中取消链路。
  - `RunStatus.CANCELED` + `error.code=CANCELED_BY_USER` 统一落地。
- 验证结果：
  - 全量 unit：`307 passed`
  - mypy：`Success (51 files)`

### 4.9 interactive-27：统一 Management API 面
- 目标：
  - 建立前端无关的统一管理契约。
- 实现重点：
  - 新增 `server/routers/management.py`。
  - 覆盖 skills/engines/runs 列表、详情、文件、SSE、pending/reply/cancel。
  - 新增 management DTO 与 interaction_count 统计接口。
- 验证结果：
  - 定向与集成：`36 passed`、`7 passed`
  - 全量 unit：`315 passed`
  - mypy：`Success (52 files)`

### 4.10 interactive-28：Web 客户端迁移到 Management API
- 目标：
  - UI 数据面统一消费 management API。
- 实现重点：
  - `ui/management/*` 适配端点与页面模板切换。
  - 旧 UI API 弃用策略 `warn|gone` + `Deprecation/Sunset/Link`。
  - run detail 对话窗口改用统一契约。
- 验证结果：
  - 目标回归：`24 passed`
  - 全量 unit：`320 passed`
  - mypy：`Success (52 files)`

### 4.11 interactive-29：决策策略与自动续跑开关
- 目标：
  - strict/auto-continue 策略矩阵落地。
- 实现重点：
  - `interactive_require_user_reply` 开关落地（默认 strict=true）。
  - 交互 kind 升级与协议扩展（`ui_hints/default_decision_policy`）。
  - 自动决策审计字段与统计外显。
- 验证结果：
  - 相关回归：`92 passed`
  - 全量 unit：`330 passed`
  - mypy：`Success (52 files)`

### 4.12 interactive-30：可观测补齐、测试矩阵、文档同步
- 目标：
  - 将 pending/interaction 观测字段补齐并稳定测试口径。
- 实现重点：
  - `RequestStatusResponse` 增加 `pending_interaction_id`、`interaction_count`。
  - 明确 `waiting_user` 下不建议继续日志轮询（`poll=false`）。
  - 扩充 unit/integration/e2e 交互路径测试矩阵。
- 验证结果：
  - 相关单测：`22 passed`
  - 集成：`3 passed`
  - 全量 unit：`332 passed`
  - mypy：`Success (52 files)`

### 4.13 interactive-31：重启恢复与孤儿进程对账
- 目标：
  - 解决服务重启后的“假活跃 run”与孤儿绑定问题。
- 实现重点：
  - 启动恢复入口：`recover_incomplete_runs_on_startup`。
  - 状态收敛矩阵：
    - `waiting_user + resumable`：保持 waiting 或 `SESSION_RESUME_FAILED`
    - `waiting_user + sticky_process`：`INTERACTION_PROCESS_LOST`
    - `queued/running`：`ORCHESTRATOR_RESTART_INTERRUPTED`
  - 清理 orphan runtime + stale trust/session + 并发槽位复位。
  - 新增恢复字段：
    - `recovery_state`
    - `recovered_at`
    - `recovery_reason`
- 验证结果：
  - 相关单测：`73 passed`
  - 集成：`4 passed`
  - 全量 unit：`337 passed`
  - mypy：`Success (52 files)`

## 5. 本轮新增/调整的重要对外契约
- Jobs：
  - `GET /v1/jobs/{request_id}` 返回交互与恢复观测字段。
  - `GET /v1/jobs/{request_id}/interaction/pending`。
  - `POST /v1/jobs/{request_id}/interaction/reply`（含幂等/冲突语义）。
  - `GET /v1/jobs/{request_id}/events`（SSE 增量日志）。
  - `POST /v1/jobs/{request_id}/cancel`。
- Temp Skill Runs：
  - `/events`、`/cancel`，并与 jobs 语义对齐。
- Management API：
  - `/v1/management/skills*`
  - `/v1/management/engines*`
  - `/v1/management/runs*`（files/file/events/pending/reply/cancel）

## 6. 本轮文档一致性补充修正
- 已补充：
  - `docs/api_reference.md`：`interaction/reply` 返回 `status` 可能为 `queued|running` 的分支说明。
  - `docs/dev_guide.md`：management run 字段清单增加恢复字段。
  - `openspec/specs/interactive-run-restart-recovery/spec.md`：`Purpose` 已从 `TBD` 改为明确语义。
  - `openspec/specs/interactive-orphan-process-reconciliation/spec.md`：`Purpose` 已从 `TBD` 改为明确语义。
- 对应检查报告：
  - `artifacts/documentation-consistency-check-and-summary-2026-02-16.md`

## 7. 验收结论
- OpenSpec：
  - 本轮 13 个 change 均已通过 `validate --strict` 并完成归档。
  - 当前 active changes：`0`（`No active changes found.`）
- 测试门禁：
  - 本轮最终全量单测：`337 passed`
  - 类型检查：`mypy server` 通过
- 交付文件：
  - 本文档：`artifacts/round-all-changes-detailed-2026-02-16.md`
  - 各 change 实现记录：`artifacts/interactive-*.md`
