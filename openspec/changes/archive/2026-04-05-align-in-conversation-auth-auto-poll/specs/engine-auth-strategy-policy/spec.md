## MODIFIED Requirements

### Requirement: Strategy service MUST expose normalized capability queries

策略服务 MUST 对会话 transport 与 runtime transport 共享同一方法语义，并允许会话侧消费 transport session behavior。

#### Scenario: conversation methods use auth_code_or_url canonical value

- **WHEN** 策略文件声明会话内人工 OAuth 返回内容输入
- **THEN** 会话 methods MUST 使用 `auth_code_or_url`
- **AND** 不得继续输出历史值 `authorization_code`

#### Scenario: waiting_auth reads session behavior from strategy

- **WHEN** 会话编排请求 engine/provider 的会话 transport 行为
- **THEN** 策略服务 MUST 返回该 transport 的 `session_behavior`
- **AND** 编排层 MUST 复用此结果生成 pending auth 读模型
