## Why

当前项目已经具备 interactive 执行能力，但“运行中 Agent 输出”的解析、转译与前端消息分发仍由各引擎差异驱动，导致协议边界不稳定、诊断路径不统一、UI 展示语义与底层流格式耦合过深。  
为了支撑 codex / gemini / iflow / opencode 的长期并行演进，需要把运行时监控、审计、解析和消息传递收敛为可版本化的正式协议。

## What Changes

- 新增运行时结构化流协议（RASP）规范，定义运行中事件信封、分类、关联标识、raw 兜底与置信度语义。
- 新增运行时审计规范，定义 PTY 采集、stdout/stderr 重建、attempt 编号、审计工件落盘与可回放要求；`fd-trace` 仅作为运行期重建依据，不作为持久化工件落盘。
- 新增前端对话消息协议（FCMP）规范，定义前端唯一消费面与从 RASP 到 FCMP 的标准转译规则。
- 统一四引擎解析 profile（codex_ndjson / gemini_json / iflow_text / opencode_ndjson）及容错链路，要求“不可解析时不得丢数据”。
- 明确 raw 事件分层策略：RASP 层保留完整 raw 证据，FCMP 转译层执行可追踪的重复回显抑制，避免对话噪声膨胀。
- 规范运行时 skill patch 注入契约，统一 completion marker、interactive 模式行为约束与注入幂等规则；注入文案从 Markdown 配置文件读取，避免硬编码。
- 修改现有 SSE 与 Run 观测 UI 规范，使其以 RASP/FCMP 作为稳定接口，而非直接暴露引擎原始流差异。
- 增加运行时协议链路关键指标（parser 命中率、fallback 率、unknown 终态率）与前端低置信度展示约束。
- 增加运行事件历史回放 API，支持按 `seq` 区间和时间区间拉取结构化事件用于复盘与诊断。
- 增强 Run 观测页排障能力：支持 `raw_ref` 一键回跳与事件关联关系视图。

## Capabilities

### New Capabilities
- `runtime-agent-stream-protocol`: 定义运行中结构化事件协议（RASP）、事件分类、字段约束、降级与兼容策略。
- `runtime-audit-and-reconstruction`: 定义运行时审计采集、stdout/stderr 重建、attempt 工件命名、fs-diff 与回放输入契约。
- `frontend-conversation-message-protocol`: 定义前端对话协议（FCMP）及 RASP->FCMP 转译规则、终态与交互事件语义。

### Modified Capabilities
- `interactive-log-sse-api`: 将 SSE 事件语义规范化为结构化运行事件流（支持协议版本、seq/cursor、raw_ref 与诊断事件）。
- `run-observability-ui`: Run 观测页改为消费统一对话协议与诊断流，弱化对引擎私有输出格式的直接依赖。
- `interactive-engine-turn-protocol`: 补充并收敛运行时 skill patch 注入契约，规范 interactive 模式 completion marker 与 ask_user 协同边界。

## Impact

- Affected code:
  - `server/services/run_observability.py`
  - `server/services/job_orchestrator.py`
  - `server/adapters/*.py`
  - `server/assets/templates/ui/run_detail.html`
  - `server/routers/jobs.py`
  - `server/routers/management.py`
  - `server/services/skill_patcher.py`
- Affected APIs:
  - `GET /v1/jobs/{request_id}/events`
  - `GET /v1/management/runs/{request_id}/events`
  - 相关 pending/reply 与 run 详情查询语义
- Artifacts/diagnostics:
  - 需要新增规范化事件落盘（如 `events.jsonl`、`parser_diagnostics.jsonl`）并与现有日志工件并存
- Testing:
  - 新增按引擎 fixture 的解析与转译一致性测试
  - 新增 SSE/前端协议一致性与容错回归用例
