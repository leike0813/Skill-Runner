## MODIFIED Requirements

### Requirement: 系统 MUST 提供可配置的引擎硬超时策略
系统 MUST 为引擎执行提供硬超时，并允许通过环境变量或运行时参数覆盖默认值；超时错误信息必须反映本次实际生效值。

#### Scenario: 运行时参数覆盖优先
- **WHEN** 运行时传入 `hard_timeout_seconds`
- **THEN** 系统使用该值作为本次执行硬超时
- **AND** 高于全局默认与环境变量

#### Scenario: Timeout 错误文案一致性
- **WHEN** 某 run 因 hard timeout 失败
- **THEN** 错误信息中的秒数应为本次实际生效值
- **AND** 不得固定为全局默认值
