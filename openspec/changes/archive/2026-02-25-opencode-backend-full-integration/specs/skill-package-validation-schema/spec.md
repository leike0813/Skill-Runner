## MODIFIED Requirements

### Requirement: runner engine 声明合同 MUST 支持“允许 + 排除”组合语义
`runner.json` 合同 MUST 支持 `engines`（可选）与 `unsupported_engines`（可选）联合声明，并满足：  
1) 两字段中的 engine 值必须来自系统支持引擎枚举（`codex/gemini/iflow/opencode`）；  
2) 两字段同时存在时不得有重复项；  
3) 缺失 `engines` 时，允许集合语义为“系统全量支持引擎”；  
4) 最终有效引擎集合 `effective_engines` 必须非空。

#### Scenario: 引擎声明包含 opencode
- **WHEN** `runner.json.engines` 或 `runner.json.unsupported_engines` 包含 `opencode`
- **THEN** 该字段通过枚举校验（前提是其余约束满足）
