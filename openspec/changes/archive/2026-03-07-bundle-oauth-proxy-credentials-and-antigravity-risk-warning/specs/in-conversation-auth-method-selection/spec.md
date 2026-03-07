## ADDED Requirements

### Requirement: 会话内高风险鉴权方式 MUST 显示风险提示
系统 MUST 在会话内鉴权 method selection 与 challenge prompt 中对高风险链路显示风险提示。

#### Scenario: method_selection options include risk marker
- **GIVEN** run 进入 `waiting_auth` 且返回 `pending_auth_method_selection`
- **AND** 某 option 对应策略中标记为高风险
- **WHEN** 系统生成 `ask_user.options`
- **THEN** 该 option label MUST 包含 `(High risk!)`
- **AND** hint 文案 MUST 包含风险提示语句

#### Scenario: single-method challenge includes risk warning
- **GIVEN** run 进入 `waiting_auth` 且仅有单一鉴权方式
- **AND** 该方式在策略中标记为高风险
- **WHEN** 系统生成 `pending_auth.prompt`
- **THEN** prompt MUST 包含高风险提示语句
