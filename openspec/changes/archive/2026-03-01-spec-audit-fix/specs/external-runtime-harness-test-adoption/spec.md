# external-runtime-harness-test-adoption Specification

## Purpose
定义引擎集成测试统一通过 harness 夹具执行、与 API/UI 契约测试物理分层的约束。

## MODIFIED Requirements

### Requirement: 引擎执行链路集成测试 MUST 统一通过 harness 夹具执行
系统 MUST 将引擎执行链路的集成测试统一接入 harness fixture，确保执行编排、审计与转译路径与新夹具一致。

#### Scenario: 引擎集成测试通过夹具入口执行
- **WHEN** 运行引擎执行链路集成测试
- **THEN** 测试入口通过 harness fixture 调用运行流程
- **AND** 测试用例不再直接复制编排逻辑
