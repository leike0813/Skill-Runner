## MODIFIED Requirements

### Requirement: waiting_user 与终态 MUST 有明确结束语义
系统 MUST 在 run 被取消时向 SSE 客户端发出可识别终态事件。

#### Scenario: 取消后事件流终止
- **GIVEN** 客户端已订阅 run 的 SSE 事件流
- **WHEN** run 因用户取消进入 `canceled`
- **THEN** 事件流发送 `status=canceled` 的终态事件
- **AND** 事件中可包含取消原因（如 `CANCELED_BY_USER`）
- **AND** 客户端可据此安全停止后续轮询或重连
