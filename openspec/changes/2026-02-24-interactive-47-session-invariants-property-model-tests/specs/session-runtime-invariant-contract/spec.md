## ADDED Requirements

### Requirement: 系统 MUST 维护 session+FCMP 不变量机器可读合同
系统 MUST 提供单一机器可读合同文件定义核心状态机与 FCMP 映射不变量。

#### Scenario: 合同文件存在且结构固定
- **WHEN** 审查不变量合同
- **THEN** 存在 `docs/contracts/session_fcmp_invariants.yaml`
- **AND** 包含 `canonical`、`transitions`、`fcmp_mapping`、`ordering_rules`

### Requirement: 测试 MUST 直接消费不变量合同
系统 MUST 由测试直接读取不变量合同，不得在测试中散落重复硬编码。

#### Scenario: 合同驱动断言
- **WHEN** 执行状态机与 FCMP 属性测试
- **THEN** 测试从合同文件加载状态集合/转移映射/配对规则

### Requirement: 合同变更 MUST 触发模型测试约束
系统 MUST 通过模型测试覆盖状态机可达性、终态约束与映射等价性。

#### Scenario: 文档漂移被测试拦截
- **WHEN** 合同与实现转移集合不一致
- **THEN** 模型测试失败并阻断回归
