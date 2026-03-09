## ADDED Requirements

### Requirement: interactive run 的鉴权等待触发 MUST 与 parser auth signal 一致
交互式 run 在进入 `waiting_auth` 时，后端 MUST 基于 parser `auth_signal` 的统一语义决策，避免 parser 与 detection 双层漂移。

#### Scenario: parser signal drives auth-required terminal mapping
- **GIVEN** run 的运行流解析结果包含 `auth_signal`
- **WHEN** 交互式 run 完成本轮终态归一化
- **THEN** 后端 MUST 依据该信号计算鉴权分类并决定是否进入 `waiting_auth`
- **AND** 不应再依赖独立 rule-registry 对 `combined_text/diagnostics` 二次匹配
