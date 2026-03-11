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
系统 MUST 规范 Agent 向用户提问时的结构化载荷，供前端稳定渲染。

#### Scenario: 提问载荷包含核心字段
- **WHEN** interaction 被创建
- **THEN** 载荷包含 `kind` 与 `prompt`
- **AND** 可选包含 `options` 与 `ui_hints`

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
系统 MUST 先判断完成证据，再决定等待用户或失败。

#### Scenario: strong evidence 优先完成
- **WHEN** 解析到 `__SKILL_DONE__`
- **THEN** 系统按完成路径收敛，不再进入等待态

#### Scenario: soft evidence 可完成并告警
- **WHEN** 未解析到 `__SKILL_DONE__`
- **AND** 未命中 ask_user 证据
- **AND** 当前回合成功提取标准化 JSON
- **AND** 当前回合输出通过 schema 校验
- **THEN** 系统可判定完成
- **AND** 记录告警 `INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER`

#### Scenario: ask_user 证据优先于 soft evidence
- **WHEN** 当前回合命中 `<ASK_USER_YAML>` 或其他 ask_user 证据
- **THEN** 系统必须优先进入等待用户路径
- **AND** generic JSON repair 不得将该回合改判为完成

#### Scenario: 提取到 JSON 但 schema 无效时保持等待并告警
- **WHEN** 未解析到 `__SKILL_DONE__`
- **AND** 未命中 ask_user 证据
- **AND** 当前回合成功提取标准化 JSON
- **AND** output schema 校验失败
- **THEN** 系统进入 `waiting_user`
- **AND** 记录告警 `INTERACTIVE_OUTPUT_EXTRACTED_BUT_SCHEMA_INVALID`

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
