## ADDED Requirements

### Requirement: 系统 MUST 定义统一的交互决策问题分类
系统 MUST 对 interactive 中间步骤的问题类型提供稳定枚举，供客户端生成对应回复控件。

#### Scenario: 返回结构化决策问题
- **WHEN** 引擎返回 `ask_user`
- **THEN** interaction 载荷包含 `kind`
- **AND** `kind` 属于受支持枚举（如 `choose_one/confirm/fill_fields/open_text/risk_ack`）

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
- **AND** 不因“未匹配固定回复结构”而拒绝

### Requirement: interactive 模式 Skill patch MUST 约束 Agent 提问载荷
系统 MUST 在 interactive 模式下向 Skill 注入提示词，要求 Agent 仅在需要用户决策时输出标准提问载荷结构。

#### Scenario: interactive 模式注入提问载荷约束
- **GIVEN** run 以 `execution_mode=interactive` 启动
- **WHEN** 系统执行 Skill patch
- **THEN** patch 内容要求 Agent 提问时输出 `kind` 与 `prompt`
- **AND** 允许附带 `options/ui_hints/default_decision_policy`
- **AND** 不要求用户回复遵循固定 JSON 结构

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
