## MODIFIED Requirements

### Requirement: Adapter MUST 提供统一 runtime 流解析接口
系统 MUST 要求所有引擎 Adapter 提供 runtime 流解析接口，输出统一结构字段（parser、confidence、session_id、assistant_messages、raw_rows、diagnostics、structured_types），并持续暴露可供 auth detection / auth challenge 构造消费的原始材料。

#### Scenario: auth-detection-ready evidence 暴露
- **WHEN** 任一引擎 Adapter 完成一次执行并返回 runtime parse / execution 结果
- **THEN** 调用方必须能够读取：
  - `stdout`
  - `stderr`
  - `pty`（如果有）
  - parser diagnostics
  - structured rows / extracted structured payloads（如适用）

#### Scenario: opencode 结构化 auth 证据可消费
- **WHEN** `opencode` 返回 provider 级结构化错误
- **THEN** runtime 材料必须允许 detector 提取 `error_name`、`status_code`、`message`、`provider_id`、`response_error_type`
