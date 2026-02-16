## ADDED Requirements

### Requirement: 系统 MUST 支持 interactive 严格回复开关
系统 MUST 提供 `interactive_require_user_reply` 开关控制交互回合是否必须等待用户回复。

#### Scenario: 未显式提供开关
- **WHEN** 客户端创建 interactive run 且未提供开关
- **THEN** 系统使用默认值 `interactive_require_user_reply=true`

#### Scenario: 显式关闭严格回复
- **WHEN** 客户端创建 interactive run 且 `interactive_require_user_reply=false`
- **THEN** 系统接受并按“允许超时自动决策”语义执行

### Requirement: reply 接口 MUST 支持自由文本回复
系统 MUST 允许客户端提交自由文本作为用户答复，不要求固定 JSON 回复结构。

#### Scenario: 提交自由文本回复
- **WHEN** 客户端调用 reply 接口提交文本答复
- **THEN** 系统接受该答复
- **AND** 不要求按 `kind` 提供固定字段对象

### Requirement: 系统 MUST 记录交互回复来源
系统 MUST 区分并持久化“用户回复”和“系统自动决策回复”。

#### Scenario: 用户主动回复
- **WHEN** 客户端调用 reply 接口提交合法回复
- **THEN** 交互历史记录 `resolution_mode=user_reply`

#### Scenario: 超时自动决策
- **WHEN** strict=false 且等待超过超时阈值
- **THEN** 系统生成自动回复并记录 `resolution_mode=auto_decide_timeout`
