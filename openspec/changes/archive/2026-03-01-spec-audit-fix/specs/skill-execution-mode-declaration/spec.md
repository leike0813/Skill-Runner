# skill-execution-mode-declaration Specification

## Purpose
定义 runner.json 中执行模式声明和存量缺失声明 skill 的 auto 兼容策略。

## MODIFIED Requirements

### Requirement: Skill runner.json MUST 声明允许的执行模式
系统 MUST 支持 Skill 在 `assets/runner.json` 中通过 `execution_modes` 声明其允许的执行模式。

#### Scenario: 合法声明
- **WHEN** Skill 包在 `runner.json` 中声明 `execution_modes`
- **THEN** 该字段是非空数组
- **AND** 每个值都属于 `auto` 或 `interactive`

#### Scenario: 缺失或非法声明
- **WHEN** `execution_modes` 缺失、为空或包含非法值
- **THEN** 新上传/更新的 Skill 包校验失败
