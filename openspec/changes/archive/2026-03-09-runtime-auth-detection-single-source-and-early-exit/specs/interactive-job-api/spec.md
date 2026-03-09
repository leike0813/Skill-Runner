## ADDED Requirements

### Requirement: Interactive run MUST transition to waiting_auth for blocked OAuth prompts
交互式运行中，当 CLI 出现 OAuth 授权码阻塞提示并被 runtime 判定为高置信鉴权需求时，系统 MUST 自动转入 `waiting_auth`，而不是长期停留在 `running`。

#### Scenario: gemini oauth code prompt blocks process
- **GIVEN** Gemini CLI 输出授权 URL 与授权码输入提示
- **AND** 进程未退出且进入阻塞等待输入
- **WHEN** runtime auth detection 命中并触发 early-exit
- **THEN** run MUST 进入 `waiting_auth`
- **AND** 现有会话鉴权恢复路径 MUST 继续可用
