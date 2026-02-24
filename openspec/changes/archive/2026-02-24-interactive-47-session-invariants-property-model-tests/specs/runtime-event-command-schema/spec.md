## MODIFIED Requirements

### Requirement: Schema 合法性 MUST 与语义不变量联合验证
系统 MUST 在 Schema 校验通过之外，继续通过不变量测试验证状态映射与事件配对语义。

#### Scenario: schema 合法但语义漂移
- **WHEN** 事件 payload 满足 schema 但状态映射不满足不变量合同
- **THEN** 属性/模型测试失败

### Requirement: 核心协议测试 MUST 使用合同驱动断言
系统 MUST 使用合同文件驱动关键协议断言，避免测试硬编码分叉。

#### Scenario: 合同驱动回归
- **WHEN** 执行协议对齐测试
- **THEN** 状态转移与 FCMP 映射断言来自统一不变量合同
