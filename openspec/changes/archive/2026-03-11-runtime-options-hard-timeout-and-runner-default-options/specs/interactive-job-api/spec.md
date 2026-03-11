## MODIFIED Requirements

### Requirement: 系统 MUST 支持任务执行模式选择
系统 MUST 支持 `auto` 与 `interactive` 两种执行模式，并保持默认向后兼容。

#### Scenario: Skill 默认 runtime options 参与 effective options 合成
- **GIVEN** skill 在 `runner.json.runtime.default_options` 声明了默认 runtime options
- **WHEN** 客户端调用 `POST /v1/jobs`
- **THEN** 系统 MUST 先应用 skill 默认值，再应用请求值覆盖
- **AND** `effective_runtime_options` 反映合成结果

#### Scenario: 请求值覆盖 skill 默认值
- **GIVEN** skill 默认值与请求体对同一 runtime option 都有声明
- **WHEN** 系统构建 `effective_runtime_options`
- **THEN** 请求体值 MUST 覆盖 skill 默认值

#### Scenario: skill 默认值非法时忽略并告警
- **GIVEN** `runner.json.runtime.default_options` 中存在未知键或非法值
- **WHEN** 系统执行 runtime option 合成
- **THEN** 系统 MUST 忽略该默认值
- **AND** MUST 记录可观测 warning（日志 + lifecycle warning/diagnostic）
- **AND** MUST NOT 因该默认值阻断 run
