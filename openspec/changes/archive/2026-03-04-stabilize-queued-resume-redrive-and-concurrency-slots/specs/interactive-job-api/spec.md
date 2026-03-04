## MODIFIED Requirements

### Requirement: reply accepted 后的 queued resume MUST 启动或明确失败
系统 MUST 保证 reply accepted 后进入的 queued resume 不会因为缺失运行资产而无限停留在 `queued`。

#### Scenario: reply accepted 后成功启动 resume
- **WHEN** 客户端提交合法 reply
- **AND** queued resume 所需 run folder 仍然存在
- **THEN** 系统返回 `status=queued`
- **AND** 后续 MUST 启动目标 attempt

#### Scenario: reply accepted 后因缺失 run folder 收敛失败
- **WHEN** 客户端提交合法 reply
- **AND** queued resume 在 redrive 前发现 run folder 已缺失
- **THEN** 系统 MAY 先返回 `status=queued`
- **AND** runtime MUST 随后将该 run 收敛到明确的 `failed`
- **AND** 系统 MUST NOT 让该 run 无限停留在 `queued`
