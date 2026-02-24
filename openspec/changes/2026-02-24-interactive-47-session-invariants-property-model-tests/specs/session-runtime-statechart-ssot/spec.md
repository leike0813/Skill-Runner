## MODIFIED Requirements

### Requirement: 系统 MUST 维护统一 canonical 状态机
系统 MUST 以 `queued/running/waiting_user/succeeded/failed/canceled` 作为唯一 canonical 状态集合，并将该集合固化在机器可读不变量合同中。

#### Scenario: canonical 生命周期合同化
- **WHEN** 审查状态机 SSOT
- **THEN** 状态集合与转移集合在 `docs/contracts/session_fcmp_invariants.yaml` 中可枚举
- **AND** 与 `server/services/session_statechart.py` 一致

### Requirement: 状态机事件映射 MUST 通过模型测试验证
系统 MUST 通过模型测试校验有限事件序列下的转移结果与实现一致。

#### Scenario: 有限序列模型等价
- **WHEN** 执行状态机模型测试
- **THEN** 合同模型与实现对同一事件序列给出一致结果
