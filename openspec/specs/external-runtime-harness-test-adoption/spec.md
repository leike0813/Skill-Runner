# external-runtime-harness-test-adoption Specification

## Purpose
TBD - created by archiving change interactive-41-external-runtime-harness-conformance. Update Purpose after archive.
## Requirements
### Requirement: 引擎执行链路集成测试 MUST 统一通过 harness 夹具执行
系统 MUST 将引擎执行链路的集成测试统一接入 harness fixture，确保执行编排、审计与转译路径与新夹具一致。

#### Scenario: 引擎集成测试通过夹具入口执行
- **WHEN** 运行引擎执行链路集成测试
- **THEN** 测试入口通过 harness fixture 调用运行流程
- **AND** 测试用例不再直接复制编排逻辑

### Requirement: API/UI 契约集成测试 MUST 与引擎集成测试物理分层
系统 MUST 将 API/UI 契约集成测试与引擎执行链路集成测试分离到不同目录和脚本入口，避免测试语义混淆。

#### Scenario: 目录与脚本入口分离
- **WHEN** 维护者查看或运行集成测试
- **THEN** 可以区分“引擎执行链路集成测试”与“API/UI 契约集成测试”
- **AND** 两类测试具有独立目录和独立执行脚本

### Requirement: 套件配置与文档 MUST 对齐新的分层路径
系统 MUST 将引擎集成套件路径、运行脚本和文档说明同步更新到分层后的目录结构。

#### Scenario: 文档与脚本路径一致
- **WHEN** 开发者按文档运行引擎集成测试或 API 集成测试
- **THEN** 文档中的路径与仓库实际路径一致
- **AND** 不出现旧目录路径导致的执行失败

