## MODIFIED Requirements

### Requirement: Adapter MUST 提供统一 runtime 流解析接口
系统 MUST 要求所有引擎 Adapter 提供 runtime 流解析接口，输出统一结构字段（parser、confidence、session_id、assistant_messages、raw_rows、diagnostics、structured_types），并暴露可供 auth detection 使用的原始材料。

#### Scenario: Adapter 暴露 auth-detection-ready evidence
- **WHEN** 任一引擎 Adapter 完成 stdout/stderr/pty 原始字节流解析
- **THEN** 返回值必须保留可供 auth detection 使用的证据
- **AND** 这些证据包括：
  - `stdout`
  - `stderr`
  - `pty`（如果有）
  - parser diagnostics
  - structured rows / extracted structured payloads（如适用）
