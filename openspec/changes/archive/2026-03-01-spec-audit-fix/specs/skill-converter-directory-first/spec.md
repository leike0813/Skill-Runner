# skill-converter-directory-first Specification

## Purpose
定义目录原地改造作为主入口的策略和 zip 包装层行为。

## MODIFIED Requirements

### Requirement: 目录原地改造是主入口
`skill-converter-agent` MUST 以“目标 skill 根目录”作为主输入入口，并在该目录中直接完成转换。

#### Scenario: 交互式调用目录模式
- **WHEN** 用户在 Agent 工具中指定一个 skill 根目录
- **THEN** Agent 在该目录内执行 `SKILL.md` 定义的改造流程（patch `SKILL.md`、生成 schema、生成 runner）
- **AND** 不要求用户先打 zip 包
