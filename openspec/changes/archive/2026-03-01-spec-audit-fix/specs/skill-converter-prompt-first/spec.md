# skill-converter-prompt-first Specification

## Purpose
定义 converter 以 prompt-first、SKILL.md 驱动的转换逻辑和三态可转换性分类。

## MODIFIED Requirements

### Requirement: Converter logic is prompt-first and SKILL.md-driven
The converter skill MUST define conversion orchestration in `SKILL.md`, including semantic analysis, task-type classification, convertibility decision, and conversion strategy execution.

#### Scenario: Semantic conversion flow executed from SKILL.md
- **WHEN** the converter skill is invoked
- **THEN** conversion decisions are produced through the staged prompt flow in `SKILL.md` instead of script-only transformation logic
