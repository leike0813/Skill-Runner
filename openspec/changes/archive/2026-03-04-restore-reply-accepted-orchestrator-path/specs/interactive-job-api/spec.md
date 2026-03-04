## ADDED Requirements

### Requirement: reply acceptance MUST 经由 canonical backend event path 发布
系统 MUST 在用户 reply 被接受后发布 canonical 的 backend acceptance event，且 canonical chat replay MUST 从这条发布路径派生可见的用户回复气泡。

#### Scenario: accepted reply 通过 canonical replay 对外可见
- **WHEN** 客户端提交一条合法的 interactive reply
- **THEN** 后端 MUST 追加一条 canonical 的 reply-accepted event
- **AND** 可见的用户聊天气泡 MUST 通过 `/chat` 或 `/chat/history` 出现
- **AND** 前端 MUST NOT 在本地自行合成该气泡
