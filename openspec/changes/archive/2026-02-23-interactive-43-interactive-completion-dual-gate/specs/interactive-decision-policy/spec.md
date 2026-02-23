## MODIFIED Requirements

### Requirement: 系统 MUST 定义统一的交互决策问题分类
The `kind` field MUST remain compatibility metadata for frontend display and MUST NOT be a backend control-plane prerequisite.

#### Scenario: kind 缺失或非预期值
- **WHEN** pending 载荷缺失 `kind` 或取值不在既有枚举中
- **THEN** 后端仍允许交互流程推进
- **AND** 客户端可回退到通用文本输入交互

### Requirement: interactive 模式 Skill patch MUST 约束 Agent 提问载荷
This requirement MUST be interpreted as optional enrichment: interactive patch MUST NOT enforce ask_user JSON structure as mandatory output.

#### Scenario: interactive 模式不强制 ask_user 结构
- **GIVEN** run 以 `execution_mode=interactive` 启动
- **WHEN** 系统执行 Skill patch
- **THEN** patch 可提示“必要时请求用户输入”
- **AND** 不把 ask_user JSON 结构作为必须产物

## ADDED Requirements

### Requirement: interactive 决策策略 MUST 定义完成证据优先级
系统 MUST 先判断完成证据，再决定等待用户或失败。

#### Scenario: strong evidence 优先完成
- **WHEN** 解析到 `__SKILL_DONE__`
- **THEN** 系统按完成路径收敛，不再进入等待态

#### Scenario: soft evidence 可完成并告警
- **WHEN** 未解析到 `__SKILL_DONE__`
- **AND** 当前回合输出通过 schema 校验
- **THEN** 系统可判定完成
- **AND** 记录告警 `INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER`

### Requirement: interactive 决策策略 MUST 支持 max_attempt 终止条件
系统 MUST 在 `max_attempt` 命中时以稳定错误终止交互回合。

#### Scenario: max_attempt 命中且无完成证据
- **WHEN** `attempt_number >= max_attempt`
- **AND** 当前回合无 strong/soft 完成证据
- **THEN** 系统终止运行并返回 `INTERACTIVE_MAX_ATTEMPT_EXCEEDED`
