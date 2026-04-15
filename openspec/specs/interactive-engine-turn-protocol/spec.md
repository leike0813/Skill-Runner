# interactive-engine-turn-protocol Specification

## Purpose
定义引擎适配层的统一回合协议、ask_user 载荷校验、模式感知补丁注入和按 execution_mode 区分的完成态判定规则。
## Requirements
### Requirement: 引擎适配层 MUST 输出统一回合协议
The target interactive turn contract MUST be JSON-only. Legacy ask-user wrappers MAY still exist in current implementation paths, but they MUST be treated as deprecated rollout behavior rather than as the formal protocol.

#### Scenario: pending turn uses pending JSON branch
- **WHEN** an interactive turn needs user input
- **THEN** the target protocol MUST be a JSON object with `__SKILL_DONE__ = false`
- **AND** it MUST include non-empty `message`
- **AND** it MUST include object `ui_hints`

#### Scenario: legacy wrapper is rollout-only
- **WHEN** documentation or migration notes mention `<ASK_USER_YAML>`
- **THEN** that wrapper MUST be labeled legacy / deprecated / current-implementation-only
- **AND** it MUST NOT be presented as the formal target protocol

### Requirement: 系统 MUST 校验 ask_user 载荷完整性
Validation of ask_user payload MUST be non-blocking: malformed ask_user MUST NOT directly fail the run and MUST NOT be treated as final business output for schema validation.

#### Scenario: ask_user 载荷不完整
- **WHEN** ask_user 缺失 `interaction_id/prompt` 等字段或类型不匹配
- **THEN** 系统忽略其结构化控制含义并回退到后端生成的 pending 基线
- **AND** run 仍可进入 `waiting_user`

### Requirement: 运行时补丁 MUST 与执行模式一致
Runtime patching for the target contract MUST describe explicit JSON-only branches rather than YAML-side-channel interaction output.

#### Scenario: interactive patch describes the union contract
- **WHEN** execution mode is `interactive`
- **THEN** the target patch contract MUST describe one union output object
- **AND** the final branch MUST require `__SKILL_DONE__ = true`
- **AND** the pending branch MUST require `__SKILL_DONE__ = false`, `message`, and `ui_hints`

#### Scenario: auto patch requires explicit final object
- **WHEN** execution mode is `auto`
- **THEN** the target patch contract MUST require a JSON object with explicit `__SKILL_DONE__ = true`

### Requirement: Adapter CLI 命令构造 MUST 与执行模式一致
系统 MUST 在构造引擎 CLI 命令时保持自动执行参数策略一致；Codex headless 自动执行参数的选择 MUST 受真实 sandbox runtime probe 结果治理，而不是只受 `LANDLOCK_ENABLED` 粗判断治理。

#### Scenario: Codex auto 模式在 sandbox 可用时保留 `--full-auto`

- **WHEN** Codex 以 `auto` 模式执行 headless start 回合
- **AND** Codex sandbox runtime probe 结果为 `available=true`
- **THEN** 命令 MUST 包含 `--full-auto`
- **AND** 命令 MUST NOT 因运行时 probe 治理而降级为 `--yolo`

#### Scenario: Codex interactive 模式在 sandbox 可用时保留 `--full-auto`

- **WHEN** Codex 以 `interactive` 模式执行 headless start 回合
- **AND** Codex sandbox runtime probe 结果为 `available=true`
- **THEN** 命令 MUST 包含 `--full-auto`

#### Scenario: Codex headless start 在 sandbox 不可用时降级为 `--yolo`

- **WHEN** Codex 构造 headless start 命令
- **AND** Codex sandbox runtime probe 结果为 `available=false`
- **THEN** 命令 MUST 包含 `--yolo`
- **AND** 命令 MUST NOT 再包含 `--full-auto`

#### Scenario: Codex headless resume 在 sandbox 不可用时降级为 `--yolo`

- **WHEN** Codex 构造 headless resume 命令
- **AND** Codex sandbox runtime probe 结果为 `available=false`
- **THEN** resume 命令 MUST 包含 `--yolo`
- **AND** resume 命令 MUST NOT 再包含 `--full-auto`

#### Scenario: Codex headless start 与 resume 共享同一 sandbox probe 真值

- **WHEN** Codex 在同一 headless runtime 中分别构造 start 与 resume 命令
- **THEN** 这两个路径 MUST 消费同一份 Codex sandbox probe 结果
- **AND** MUST NOT 由 start/resume 各自实现独立的 sandbox 可用性判定分支

### Requirement: 完成态判定 MUST 按 execution_mode 区分
The target contract MUST remove soft-completion semantics from normative completion rules.

#### Scenario: interactive final turn requires explicit final branch
- **WHEN** an interactive turn is complete under the target contract
- **THEN** it MUST emit a JSON object with `__SKILL_DONE__ = true`
- **AND** business fields MUST satisfy the skill output schema

#### Scenario: legacy soft completion is not the target rule
- **WHEN** historical rollout notes mention completion without explicit done marker
- **THEN** they MUST be labeled as legacy rollout context
- **AND** they MUST NOT be presented as the target completion rule

### Requirement: 运行时 skill patch 注入 MUST 模块化且顺序固定
系统 MUST 按固定模块顺序注入运行时 patch 到 `SKILL.md`。

#### Scenario: patch 顺序固定
- **WHEN** 运行时执行 skill patch
- **THEN** 注入顺序为：
  1. runtime enforcement
  2. artifact redirection（若存在 artifacts）
  3. output format contract
  4. output schema specification（若 output schema 可用）
  5. mode patch（auto 或 interactive）

#### Scenario: mode 注入互斥
- **WHEN** execution_mode=`interactive`
- **THEN** 仅注入 interactive mode patch
- **AND** 不注入 auto mode patch

### Requirement: assistant 文本 JSON 提取 MUST be constrained in interactive mode
interactive 模式下从 assistant 文本提取标准化 JSON MUST 受 ask-user 证据与候选边界约束。

#### Scenario: embedded evidence json must not become final payload
- **WHEN** assistant 文本包含正文、证据数组或示例 JSON 片段
- **AND** 这些 JSON 不是最外层最终结果
- **THEN** 系统 MUST NOT 将其提升为 final payload

#### Scenario: assistant-text extraction only applies without ask_user evidence
- **WHEN** 当前 attempt 命中 `<ASK_USER_YAML>`
- **THEN** assistant 文本 JSON 提取 MUST NOT 参与 final/soft-completion 判定

### Requirement: repair MUST NOT decide completion
Repair MUST act as same-attempt schema convergence only; it MUST NOT invent waiting-state control flow or upgrade deprecated legacy ask-user payloads into compliant final outputs.

#### Scenario: repair stays inside one attempt
- **WHEN** a turn fails schema validation and enters repair
- **THEN** each repair retry MUST remain inside the current attempt
- **AND** repair MUST NOT increment `attempt_number`

#### Scenario: repair cannot transform legacy ask-user into primary protocol
- **WHEN** a turn only provides legacy ask-user wrapper evidence
- **THEN** repair MUST NOT treat that wrapper as the target compliant protocol
- **AND** future compliant behavior MUST instead produce the pending JSON branch

### Requirement: Interactive Prompt Contract Uses JSON Pending or Final Branches

Interactive engine prompts MUST instruct the agent to emit the JSON union contract only.

#### Scenario: Pending-turn guidance forbids legacy ask-user blocks
- **WHEN** runtime patches a skill for interactive execution
- **THEN** the prompt MUST instruct the agent to emit either:
  - a final JSON object with `__SKILL_DONE__ = true`, or
  - a pending JSON object with `__SKILL_DONE__ = false`, `message`, and `ui_hints`
- **AND** the prompt MUST explicitly forbid `<ASK_USER_YAML>` as a valid output protocol

### Requirement: repair protocol MUST expose explicit round semantics
The target engine-turn protocol MUST describe repair as attempt-internal rounds rather than an implicit retry side effect.

#### Scenario: engine turn stays on the same attempt during repair
- **WHEN** a turn enters output convergence
- **THEN** the protocol model MUST describe repair work as `internal_round`s inside the current attempt
- **AND** it MUST reserve orchestrator repair events that carry both `attempt_number` and `internal_round_index`

### Requirement: repair MUST NOT create competing executors
Engine adapters and parsers MAY contribute repaired candidates, but they MUST NOT become separate repair authorities.

#### Scenario: adapter repair is subordinate to orchestrator ownership
- **WHEN** an adapter or parser applies deterministic repair
- **THEN** the resulting candidate MUST be treated as input to the orchestrator convergence executor
- **AND** the protocol MUST NOT describe adapter-level repair as a parallel governance path

### Requirement: Legacy Ask-User Markup Does Not Populate Waiting Payloads

Interactive engine turn processing MUST reject deprecated ask-user wrappers as a
data source for waiting payload enrichment.

#### Scenario: Deprecated ask-user markup cannot supply prompt metadata
- **WHEN** model output contains `<ASK_USER_YAML>` or similar legacy ask-user
  markup
- **THEN** runtime MUST NOT populate canonical `PendingInteraction` fields from
  that markup
- **AND** only a valid pending JSON branch may supply rich waiting payload data

### Requirement: Interactive Turn Protocol Distinguishes Formal Branches From Compatibility Paths

Interactive turn processing MUST keep the formal contract and compatibility
fallbacks distinct.

#### Scenario: pending branch remains the formal waiting source
- **WHEN** an interactive turn produces a valid pending JSON branch
- **THEN** runtime MUST project that branch into canonical `PendingInteraction`
- **AND** this path MUST be preferred over compatibility waiting fallback

#### Scenario: missing explicit branch may still soft-complete
- **WHEN** an interactive turn does not resolve a valid final or pending branch
- **AND** business output remains schema-valid
- **THEN** runtime MAY still classify the turn as soft completion
- **AND** that classification MUST remain a compatibility path

#### Scenario: compatibility waiting fallback stays generic
- **WHEN** an interactive turn reaches waiting fallback instead of a valid
  pending branch
- **THEN** runtime MUST use the default pending payload
- **AND** it MUST NOT restore deprecated ask-user enrichment

