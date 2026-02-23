## Context

当前 Skill Runner 的 interactive 执行链路已具备运行与交互能力，但运行时观测仍以“stdout/stderr 增量 + 适配器末态解析”为主，导致以下问题：

- 运行中事件语义未形成正式协议，前端和引擎输出格式存在隐式耦合。
- 不同引擎（结构化 JSON 流与纯文本流）的解析策略分散，缺少统一置信度与降级语义。
- 审计工件以当前运行日志为主，缺少 attempt 粒度、重建证据和可回放规范。
- skill patch 关注点仍偏向 artifact 重定向与 ask_user 约束，缺少 completion contract 的统一注入规则。

本变更以 `references/agent-test-env` 中已验证的方法为参考，将运行时监控、解析、消息传递和 patch 注入升级为可版本化规范。

## Goals / Non-Goals

**Goals:**
- 定义并落地统一的运行中结构化事件协议（RASP），覆盖 lifecycle/agent/interaction/tool/artifact/diagnostic/raw。
- 定义运行时审计构建规范（PTY + split reconstruction + attempt 工件），并约束 `fd-trace` 不作为持久化日志落盘。
- 定义前端唯一消费协议（FCMP）及 RASP->FCMP 转译规则。
- 统一四类解析 profile（codex_ndjson / gemini_json / iflow_text / opencode_ndjson）的分类、置信度和兜底行为。
- 规范 skill patch 的 completion contract 注入方式，特别是 interactive 模式下的补丁语义，并要求注入文案来自 Markdown 配置文件。
- 增加历史回放能力：支持按 `seq`/时间区间拉取 RASP 事件用于复盘。
- 增强 Run 观测页排障可视化：`raw_ref` 快速回跳与事件关联关系视图。

**Non-Goals:**
- 不在本变更中引入 ACP 或替换现有 REST/SSE 主体接口。
- 不改变现有 run 业务状态机（queued/running/waiting_user/succeeded/failed/canceled）。
- 不将前端直接切换到新 UI 框架；仅规范消息协议与转译流程。

## Decisions

### Decision 1: 运行时新增 RASP 作为后端稳定事件层

采用 `rasp/1.0` 作为运行域标准事件信封，核心字段包括 `protocol_version/run_id/seq/ts/source/event/data/correlation/raw_ref/attempt_number`。  
所有引擎运行中输出先归一化为 RASP，再进入下游（SSE、存档、前端转译）。

并统一游标与尝试语义：
- `seq`: 同一 `run_id` 下全局单调递增（跨 attempt 连续）。
- `cursor`: 客户端已消费到的最后 `seq`。
- `attempt_number`: interactive 模式下“初始请求=1，每次用户 reply 触发新回合递增”；auto 模式固定为 `1`。

备选方案：
- 直接将引擎原始事件推给前端：实现简单但耦合高，且难以统一诊断与回放。
- 仅保留 stdout/stderr 文本：无法表达 session/tool/interaction 等结构化语义。

### Decision 2: 运行时审计采用 attempt 编号工件与非持久化 trace 重建

每次运行/恢复回合都写入 attempt 编号审计工件（如 `meta.N.json/stdout.N.log/stderr.N.log/pty-output.N.log/fs-diff.N.json`），并允许在运行期使用 trace 进行 stdout/stderr 重建，但 `fd-trace` 不落盘持久化。  
`fs-diff` 计算时忽略审计目录，避免观测系统污染业务 diff。

备选方案：
- 仅保留最终 stdout/stderr：无法定位“为何解析错误”与“流分离依据”。
- 仅保留 PTY 合并流：无法稳定区分 stdout/stderr。

### Decision 3: 解析器采用“profile + 置信度 + raw 兜底”策略

为每个引擎定义 parser profile：
- codex: `codex_ndjson`
- gemini: `gemini_json`
- iflow: `iflow_text`
- opencode: `opencode_ndjson`

解析失败或分类不确定时必须降级为 `raw.* + diagnostic.warning`，禁止静默吞数据。  
同时输出 `parse_confidence` 与诊断码，便于前端和排障系统解释不确定性。
并约束容错链路顺序（NDJSON 行级容错、Gemini 响应块提取、iFlow 文本降级）为固定实现，避免各引擎实现分叉。

备选方案：
- 单一解析器策略：难以应对各引擎流格式差异和漂移。

### Decision 4: FCMP 作为前端唯一消费协议

前端仅消费 `fcmp/1.0`，不直接解析引擎输出或 RASP 细节。  
转译层负责将 RASP 映射为 `conversation.started/assistant.message.final/user.input.required/conversation.completed/conversation.failed/diagnostic.warning` 等稳定事件。
UI 必须将低置信度与诊断信息独立呈现，防止原始噪声影响主对话阅读。
并在转译层执行“raw 回显规范化抑制”：
- RASP 层完整保留 raw 事件，不做删除。
- FCMP 层抑制与 `assistant.message.final` 重复的 raw 连续回显块（默认阈值 `>=3` 行）。
- 每次抑制都发出 `RAW_DUPLICATE_SUPPRESSED` 诊断事件并记录抑制数量，确保可追踪。

备选方案：
- 前端直接消费 RASP：扩展能力强但 UI 复杂度高，不利于稳定交付。

### Decision 5: skill patch 注入 completion contract 与执行模式补丁分层

保留现有“artifact 重定向 + 模式语义”补丁分层，并新增 completion contract 注入规则：
- 完成时必须发出完成标记（仅使用大写 `__SKILL_DONE__=true`；优先内嵌于最终 JSON，非 JSON 结果允许单独 done 对象）。
- interactive 模式下，不得在未完成时提前输出 done 标记。
- patch 注入必须幂等，避免重复附加协议段落。
- completion contract 文案不允许硬编码在 patcher 中，必须从可版本化的 Markdown 配置文件加载。
- 单轮输出出现多个 done marker 时以首个 marker 为准，后续 marker 忽略；多轮流程在首次命中 done marker 后必须结束。

备选方案：
- 由引擎约定隐式完成：无法对跨引擎完成态判定建立可验证合同。

### Decision 6: 回放 API 与前端关联可视化进入首版规范

在现有 SSE 实时流基础上，新增历史回放 API：
- 支持按 `seq` 区间拉取结构化事件。
- 支持按时间区间拉取结构化事件。

并要求 Run 观测 UI 提供关联排障能力：
- 基于 `raw_ref` 一键跳转原始日志区间。
- 基于 `correlation` 字段展示最小可用事件关联关系视图（如 request/reply/tool/artifact 关联）。

备选方案：
- 仅保留 SSE 实时消费：无法覆盖断线后诊断与历史复盘。
- 仅输出事件列表不做关联可视化：定位跨事件因果关系成本高。

## Risks / Trade-offs

- [风险] 事件协议升级导致现有 SSE 消费方不兼容  
  → Mitigation: 本变更直接以 `run_event` 为主路径，避免长期双轨并存造成技术债务。

- [风险] 运行期 trace + PTY 审计引入运行时开销  
  → Mitigation: 提供可配置开关与采样策略；默认保留关键工件，重载场景下可降级。

- [风险] iFlow 文本解析误判  
  → Mitigation: 降级到 raw+warning，避免错误结构化；通过 fixture 回归持续收敛规则。

- [风险] completion marker 与现有 skill 习惯冲突  
  → Mitigation: 统一要求仅支持大写 `__SKILL_DONE__`，并在 patch 文案和测试中强制校验。

- [风险] Markdown 配置文件缺失或格式不合法导致 patch 失败  
  → Mitigation: 启动时校验配置文件存在与可读性，缺失时 fail-fast 并输出明确错误。

## Migration Plan

1. 在后端新增 RASP 数据模型与事件构建器，保留现有 run 状态更新路径。
2. 在 run observability 层引入统一事件流输出（新增 `run_event`），并收敛为单一路径。
3. 引入 parser profile 组件，按引擎实现解析与诊断映射；落盘 `events.jsonl`、`parser_diagnostics.jsonl`。
4. 新增 FCMP 转译器并接入 management run 页面，按统一对话协议替换旧渲染路径。
5. 在 FCMP 转译层实现 raw 回显抑制（保留 RASP 原始记录），并输出抑制诊断事件。
6. 扩展 skill patcher：从 Markdown 配置文件读取 completion contract，补充 interactive 模式约束与幂等检查。
7. 在事件层实现 `seq/cursor/attempt_number/raw_ref` 一致语义，确保重连与回放可重建。
8. 在 `meta.N.json` 增加重建摘要字段，并补充运行指标（命中率/fallback/unknown）。
9. 增加历史回放 API（seq/time 区间），并与 cursor 续传规则协同。
10. 在 Run 观测页接入 `raw_ref` 快速回跳与事件关联关系视图。
11. 通过 fixture 回归（codex/gemini/iflow/opencode）验证解析、转译与终态判定一致性。

Rollback:
- 关闭 RASP/FCMP 开关，回退到原 stdout/stderr 事件流消费；
- 保留新增审计文件不影响运行主路径，回滚仅需切断新转译链路。

## Open Questions

- 是否在首版将 `run_event` 作为默认 SSE 事件名，还是先以 query flag 控制新协议输出。
- `opencode` 在主项目中的接入优先级（先协议就绪后接引擎，或同步落地）。

## Follow-up Candidates (Out of Scope)

- 属性测试与 fuzz 测试（后续单独 change）。
- 跨引擎统一 tool 生命周期增强事件（待样本与解析稳定后推进）。
- 迁移完成后下线残余 legacy 事件（后续单独 change）。
- 完整 runbook 与故障演练脚本（后续运维建设）。
