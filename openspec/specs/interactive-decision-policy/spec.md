# interactive-decision-policy Specification

## Purpose
定义 interactive 模式下的交互决策策略，包括提问载荷结构、用户回复接受规则、完成证据优先级和 max_attempt 终止条件。
## Requirements
### Requirement: 系统 MUST 定义统一的交互决策问题分类
The `kind` field MUST remain compatibility metadata for frontend display and MUST NOT be a backend control-plane prerequisite.

#### Scenario: kind 缺失或非预期值
- **WHEN** pending 载荷缺失 `kind` 或取值不在既有枚举中
- **THEN** 后端仍允许交互流程推进
- **AND** 客户端可回退到通用文本输入交互

### Requirement: 系统 MUST 统一 Agent 提问载荷结构
The target pending payload MUST be represented by the pending branch of the interactive union contract.

#### Scenario: pending payload uses message plus ui_hints
- **WHEN** the system creates a target interactive prompt payload
- **THEN** the source contract MUST be a JSON object with `__SKILL_DONE__ = false`
- **AND** it MUST contain non-empty `message`
- **AND** it MUST contain object `ui_hints`

#### Scenario: kind remains compatibility metadata
- **WHEN** frontend classification needs `kind`
- **THEN** `kind` MAY remain compatibility metadata inside `ui_hints` or projected pending payloads
- **AND** it MUST NOT be a backend control-plane prerequisite

### Requirement: 系统 MUST 接受用户自由文本回复
系统 MUST 将用户回复视为自由文本输入，而不是按 `kind` 强制固定 JSON 结构。

#### Scenario: 各 kind 下均可提交自由文本
- **GIVEN** 任意受支持 `kind`
- **WHEN** 客户端提交自由文本回复
- **THEN** 系统接受该回复并进入后续编排流程
- **AND** 不因"未匹配固定回复结构"而拒绝

### Requirement: interactive 模式 Skill patch MUST 约束 Agent 提问载荷
This requirement MUST be interpreted as optional enrichment: interactive patch MUST NOT enforce ask_user JSON structure as mandatory output.

#### Scenario: interactive 模式不强制 ask_user 结构
- **GIVEN** run 以 `execution_mode=interactive` 启动
- **WHEN** 系统执行 Skill patch
- **THEN** patch 可提示"必要时请求用户输入"
- **AND** 不把 ask_user JSON 结构作为必须产物

### Requirement: auto 模式 Skill patch MUST 不注入交互提问约束
系统 MUST 在 auto 模式下保持自动执行提示词，不注入 interactive 提问载荷约束。

#### Scenario: auto 模式保持自动执行语义
- **GIVEN** run 以 `execution_mode=auto` 启动
- **WHEN** 系统执行 Skill patch
- **THEN** patch 内容保留自动执行约束
- **AND** 不包含 interactive 提问载荷字段约束（如 `kind/prompt/options/ui_hints`）

### Requirement: 系统 MUST 提供自动决策策略提示字段
系统 MUST 在 interaction 载荷中提供自动决策策略提示，供超时自动决策路径消费。

#### Scenario: interaction 提供 default_decision_policy
- **WHEN** interaction 被创建
- **THEN** 载荷包含 `default_decision_policy`
- **AND** 该字段可用于 strict=false 的自动决策回合

### Requirement: interactive 决策策略 MUST 定义完成证据优先级
The target policy MUST prioritize explicit final/pending branches over legacy soft-completion evidence.

#### Scenario: explicit final branch wins completion
- **WHEN** a turn emits a compliant final JSON object
- **THEN** the system MUST converge on completion

#### Scenario: explicit pending branch wins waiting
- **WHEN** a turn emits a compliant pending JSON object
- **THEN** the system MUST converge on waiting for user input

#### Scenario: legacy soft completion is not the target decision rule
- **WHEN** rollout notes mention soft completion
- **THEN** they MUST be labeled legacy/deprecated context
- **AND** they MUST NOT be described as the target decision policy

### Requirement: interactive 决策策略 MUST 支持 max_attempt 终止条件
系统 MUST 在 `max_attempt` 命中时以稳定错误终止交互回合。

#### Scenario: max_attempt 命中且无完成证据
- **WHEN** `attempt_number >= max_attempt`
- **AND** 当前回合无 strong/soft 完成证据
- **THEN** 系统终止运行并返回 `INTERACTIVE_MAX_ATTEMPT_EXCEEDED`

### Requirement: ask_user 证据 MUST 高于 generic JSON repair
interactive 模式下，ask_user 证据 MUST 作为最高优先级门禁，generic JSON repair 不得覆盖其判定。

#### Scenario: ask_user yaml suppresses generic repair
- **WHEN** assistant 文本同时包含 `<ASK_USER_YAML>` 与可提取 JSON
- **THEN** 系统 MUST 优先判定为需要用户输入
- **AND** generic repair MUST NOT 将该回合改判为 soft completion

### Requirement: lifecycle MUST emit warnings for risky soft-completion inputs
系统 MUST 对会导致误判风险的 structured output 条件输出稳定 warning。

#### Scenario: permissive schema warning
- **WHEN** interactive 模式通过 soft completion 完成
- **AND** output schema 过宽松
- **THEN** 系统 MUST 记录 `INTERACTIVE_SOFT_COMPLETION_SCHEMA_TOO_PERMISSIVE`

#### Scenario: extracted json invalid warning
- **WHEN** interactive 模式提取到标准化 JSON
- **AND** output schema 校验失败
- **THEN** 系统 MUST 记录 `INTERACTIVE_OUTPUT_EXTRACTED_BUT_SCHEMA_INVALID`
- **AND** run MUST 保持 `waiting_user`

### Requirement: Phase 4 Preserves Soft Completion

Phase 4 MUST NOT tighten final completion semantics.

#### Scenario: Soft completion remains a legacy completion path
- **WHEN** an interactive attempt produces schema-valid business output without
  an explicit done marker
- **THEN** runtime MAY continue to treat that attempt as a soft completion
- **AND** this phase MUST NOT convert that path into waiting-only behavior

### Requirement: Interactive Completion Gate Keeps Stable Compatibility Codes

Phase 5 MUST preserve the existing warning and diagnostic codes for
compatibility completion and invalid structured output handling.

#### Scenario: soft completion keeps the established warning code
- **WHEN** an interactive attempt completes through soft completion
- **THEN** runtime MUST continue to emit
  `INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER`

#### Scenario: permissive schema keeps the existing compatibility warning
- **WHEN** an interactive attempt completes through soft completion
- **AND** the output schema is too permissive
- **THEN** runtime MUST continue to emit
  `INTERACTIVE_SOFT_COMPLETION_SCHEMA_TOO_PERMISSIVE`

#### Scenario: invalid structured output keeps the existing waiting warning
- **WHEN** an interactive attempt produces structured output
- **AND** that output fails schema validation
- **THEN** runtime MUST continue to emit
  `INTERACTIVE_OUTPUT_EXTRACTED_BUT_SCHEMA_INVALID`

### Requirement: Explicit Branches Define The Formal Contract

Interactive decision policy MUST treat the final and pending union branches as
the formal contract even while compatibility paths remain enabled.

#### Scenario: compatibility completion is not promoted to a formal branch
- **WHEN** soft completion is used
- **THEN** runtime MAY complete the attempt
- **AND** soft completion MUST remain documented as a compatibility path rather
  than the formal output contract

### Requirement: ask_user 证据 MUST 退役为 legacy 兼容语义
`<ASK_USER_YAML>` MUST be described as deprecated compatibility semantics rather than as a formal protocol.

#### Scenario: legacy wrapper is not the formal contract
- **WHEN** `<ASK_USER_YAML>` is referenced in migration or compatibility notes
- **THEN** it MUST be explicitly labeled deprecated
- **AND** the formal target contract MUST remain the pending JSON branch

### Requirement: repair decision ownership MUST belong to the orchestrator convergence executor
Interactive repair decisions MUST be owned by a single orchestrator-side convergence executor.

#### Scenario: parser repair cannot independently classify the turn
- **WHEN** deterministic generic repair produces a usable candidate
- **THEN** the candidate MUST be evaluated by the orchestrator-owned convergence executor
- **AND** parser-level repair MUST NOT independently classify the turn as complete or waiting

#### Scenario: waiting fallback remains outside repair ownership in current runtime
- **WHEN** current runtime behavior derives `waiting_user` from legacy ask-user or invalid-structured-output heuristics
- **THEN** those paths MUST be documented as lifecycle fallback semantics
- **AND** they MUST remain outside target repair ownership until a later implementation phase switches the source

