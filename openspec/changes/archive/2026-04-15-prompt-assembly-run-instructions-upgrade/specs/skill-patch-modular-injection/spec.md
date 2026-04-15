## ADDED Requirements

### Requirement: Prompt organization MUST separate run-root instructions from runtime SKILL patching
系统 MUST 将 run-root instruction file 与 runtime `SKILL.md` patch 视为两个独立层次，禁止再次通过 skill prompt prefix 混合两者职责。

#### Scenario: prompt organization layers
- **WHEN** runtime 组织引擎可见提示信息
- **THEN** run-root instruction file MUST 承载 engine-agnostic 全局执行约束
- **AND** runtime `SKILL.md` MUST 继续承载 skill-local runtime patch 模块
- **AND** 最终 CLI prompt MUST 仅由 invoke line 与 body prompt 组成
