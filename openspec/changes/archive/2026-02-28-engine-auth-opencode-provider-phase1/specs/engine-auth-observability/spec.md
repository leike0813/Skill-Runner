## ADDED Requirements

### Requirement: 鉴权会话状态机 MUST 在 input 体系下统一语义
系统 MUST 在统一 input 接口下保持跨引擎一致的状态语义。

#### Scenario: 后台自动编排阶段
- **WHEN** 会话处于后台自动输入阶段
- **THEN** 状态为 `waiting_orchestrator`

#### Scenario: 等待用户输入阶段
- **WHEN** 会话已到达用户输入点（URL/API key/code）
- **THEN** 状态为 `waiting_user`

#### Scenario: 输入已提交等待结果
- **WHEN** 会话已接受用户输入且等待 CLI 收敛
- **THEN** 状态为 `code_submitted_waiting_result`

### Requirement: OpenCode Google 清理动作 MUST 可审计
系统 MUST 在会话快照中记录 Google AntiGravity 账号清理动作结果。

#### Scenario: 清理成功审计
- **WHEN** Google 清理成功
- **THEN** 会话快照包含 `audit.google_antigravity_cleanup` 成功结果

#### Scenario: 清理失败审计
- **WHEN** Google 清理失败
- **THEN** 会话快照包含失败信息并进入 `failed`
