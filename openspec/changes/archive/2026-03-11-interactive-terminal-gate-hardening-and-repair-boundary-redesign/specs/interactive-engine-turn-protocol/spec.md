## ADDED Requirements
### Requirement: assistant 文本 JSON 提取 MUST be constrained in interactive mode
interactive 模式下从 assistant 文本提取标准化 JSON 必须受 ask-user 证据与候选边界约束。

#### Scenario: embedded evidence json must not become final payload
- **WHEN** assistant 文本包含正文、证据数组或示例 JSON 片段
- **AND** 这些 JSON 不是最外层最终结果
- **THEN** 系统 MUST NOT 将其提升为 final payload

#### Scenario: assistant-text extraction only applies without ask_user evidence
- **WHEN** 当前 attempt 命中 `<ASK_USER_YAML>`
- **THEN** assistant 文本 JSON 提取 MUST NOT 参与 final/soft-completion 判定

### Requirement: repair MUST NOT decide completion
repair 只能修复已识别完成候选的 payload / artifact，不得负责提升当前回合为完成态。

#### Scenario: repair cannot upgrade ask_user turn
- **WHEN** 当前回合命中 ask_user 证据
- **THEN** repair MUST NOT 将该回合转化为 final output
