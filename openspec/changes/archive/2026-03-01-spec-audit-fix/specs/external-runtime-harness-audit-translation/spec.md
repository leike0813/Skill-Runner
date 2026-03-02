# external-runtime-harness-audit-translation Specification

## Purpose
定义外部 harness 复用核心 RASP/FCMP 转译链路和按 attempt 组织审计工件的约束。

## MODIFIED Requirements

### Requirement: Harness MUST 复用项目核心 RASP/FCMP 转译链路
系统 MUST 复用本项目既有运行时协议实现（RASP/FCMP）进行解析与转译，禁止在 harness 内实现并维护另一套语义不一致的核心转译逻辑。

#### Scenario: 转译语义一致
- **WHEN** harness 对同一 run attempt 生成对话事件
- **THEN** 事件协议版本、类型与字段语义与项目核心 RASP/FCMP 实现一致
- **AND** 不因 harness 渲染层引入额外协议分叉
