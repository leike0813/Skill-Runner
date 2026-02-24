# session-runtime-invariant-contract Specification

## Purpose
定义 session+FCMP 核心不变量的机器可读合同，以及其测试守护策略。

## Requirements

### Requirement: 系统 MUST 维护单一不变量合同文件
系统 MUST 维护单一机器可读文件作为 session+FCMP 核心不变量的 SSOT。

#### Scenario: 合同文件存在
- **WHEN** 审查不变量定义
- **THEN** 存在 `docs/contracts/session_fcmp_invariants.yaml`
- **AND** 文件包含 `canonical`、`transitions`、`fcmp_mapping`、`ordering_rules`

### Requirement: 测试 MUST 直接消费不变量合同
系统 MUST 由测试直接读取不变量合同，不得在多个测试中重复硬编码关键状态和映射。

#### Scenario: 合同驱动测试
- **WHEN** 执行状态机/映射测试
- **THEN** 测试使用统一合同加载器读取状态集合、转移集合和配对规则

### Requirement: 模型测试 MUST 覆盖状态机与映射语义
系统 MUST 通过模型测试守护关键语义不变量。

#### Scenario: 状态机模型一致
- **WHEN** 对有限事件序列进行模型回放
- **THEN** 合同模型与实现模型得到相同状态结果

#### Scenario: FCMP 映射与配对一致
- **WHEN** 生成 FCMP 事件序列
- **THEN** `conversation.state.changed` 三元组属于合同映射
- **AND** reply/auto-decide 事件满足配对规则
