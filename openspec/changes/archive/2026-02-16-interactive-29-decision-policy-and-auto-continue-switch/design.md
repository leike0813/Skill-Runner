## Context

目前 interactive 流程已具备 ask_user/pending/reply 能力，但存在两个缺口：
1. 中间问题缺少统一分类与响应约定，客户端难以做稳定表单/控件映射。
2. 用户未回复时只能等待（或 sticky_process 超时失败），缺少“自动决策继续”的显式策略开关。

## Goals

1. 建立最小可执行的交互决策协议（问题类型、提问载荷、默认决策规则）。
2. 引入 strict 开关，在“强制人工决策”与“超时自动决策”之间可切换。
3. 明确 `resumable/sticky_process` 在 strict on/off 下的状态机差异。
4. 将自动决策行为纳入可观测与审计历史。

## Non-Goals

1. 不定义行业级复杂 DSL，仅做基础协议与枚举。
2. 不改变引擎能力分层（`resumable|sticky_process`）本身。
3. 不新增 UI 页面，仅提供可被 UI 消费的稳定语义。

## Prerequisite

- `interactive-05-engine-session-resume-compatibility`
- `interactive-10-orchestrator-waiting-user-and-slot-release`
- `interactive-11-session-timeout-unification-and-consumer-refactor`
- `interactive-20-adapter-turn-protocol-and-mode-aware-patching`

## Design

### 1) 决策协议（Interaction Decision Contract）

扩展 `interaction` 载荷，增加统一字段：
- `kind`（枚举）：
  - `choose_one`：从选项中选择一个
  - `confirm`：是/否确认
  - `fill_fields`：补齐字段
  - `open_text`：自由澄清文本
  - `risk_ack`：风险确认
- `prompt`：向用户展示的问题文本
- `options`：可选选项列表（可空）
- `ui_hints`：可选 UI 提示（展示建议，不参与 reply 校验）
- `default_decision_policy`：自动决策策略提示（如 `engine_judgement|safe_default|abort`）

回复规范：
- 用户回复统一为自由文本；
- 系统不按 `kind` 对用户回复施加固定 JSON 结构约束；
- 如前端需要结构化控件，可基于 `kind/options/ui_hints` 自行组织交互并最终回填为文本。

### 1.1) Skill patch 提示词分流（auto vs interactive）

在 `interactive-20` 已完成“patch 分步化”的基础上，本 change 补齐交互决策协议对应的提示词约束：

1. `execution_mode=auto`
- 继续注入自动执行提示词（如“默认自行决策并继续执行，除非出现不可继续错误”）；
- 不要求输出交互提问载荷。

2. `execution_mode=interactive`
- 注入交互提问提示词，要求 Agent 在需要用户决策时输出结构化提问载荷：
  - 必含：`kind`, `prompt`
  - 可选：`options`, `ui_hints`
  - 应附：`default_decision_policy`
- 明确用户回复由系统以自由文本转发，Agent 不得要求固定 JSON 回复结构。

3. 两种模式共通
- artifact 输出目录 patch 始终启用，不受 execution_mode 影响；
- 决策协议相关 patch 仅在 interactive 模式启用，避免污染 auto 语义。

### 2) strict 开关

新增 runtime option：
- `interactive_require_user_reply: boolean`
- 默认值：`true`（保持当前行为）

语义：
- `true`：严格需要用户回复
- `false`：允许超时后自动决策继续

### 3) 行为矩阵

#### A. `interactive_require_user_reply=true`

1. `resumable`
- 进入 `waiting_user` 后不自动推进；
- run 可长期停留未完成（直到用户回复或显式取消）。

2. `sticky_process`
- 进入 `waiting_user` 后启动 `session_timeout_sec` 计时；
- 超时后终止进程并失败（`INTERACTION_WAIT_TIMEOUT`）。

#### B. `interactive_require_user_reply=false`

1. `resumable`
- 进入 `waiting_user` 后启动 `session_timeout_sec` 计时；
- 超时后系统自动生成“未收到用户回复，请按自身判断继续”回复；
- 通过 resume 启动下一回合继续执行。

2. `sticky_process`
- 进入 `waiting_user` 后启动 `session_timeout_sec` 计时；
- 超时后向驻留进程注入自动决策指令，继续执行，不立即失败。

### 4) 自动决策回复封装

系统生成统一自动回复封装：
- `source = "auto_decide_timeout"`
- `interaction_id`
- `reason = "user_no_reply"`
- `policy = default_decision_policy`
- `instruction = "User did not respond in time. Continue with your best judgement ..."`

要求：
- 自动回复与人工回复走同一编排入口，避免分叉实现。

### 5) 审计与可观测

交互历史新增字段：
- `resolution_mode: user_reply | auto_decide_timeout`
- `resolved_at`
- `auto_decide_reason?`

状态侧可选字段：
- `auto_decision_count`
- `last_auto_decision_at`

## Risks & Mitigations

1. **风险：自动决策导致与用户期望偏差**
   - 缓解：默认 strict=true，需显式关闭；并完整记录自动决策审计信息。
2. **风险：non-resumable 自动注入时序竞争**
   - 缓解：复用同一进程消息队列入口，保证 interaction_id 幂等消费。
3. **风险：kind 与提问载荷字段扩展过快**
   - 缓解：先固定五类基础 kind 与最小提问字段，后续再扩展。
