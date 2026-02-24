## ADDED Requirements

### Requirement: 系统 MUST 为核心事件/命令维护统一 JSON Schema 合同
系统 MUST 提供单一 Schema SSOT 覆盖 FCMP/RASP/orchestrator/pending/history/resume-command。

#### Scenario: Schema 统一入口
- **WHEN** 运行时构造上述协议对象
- **THEN** 校验必须通过统一 registry 入口执行

### Requirement: 写入路径 MUST 严格校验
系统 MUST 在持久化/输出前校验协议对象，不合规对象不得写入。

#### Scenario: FCMP 写入校验失败
- **WHEN** 生成的 FCMP 事件不满足 schema
- **THEN** 系统抛出 `PROTOCOL_SCHEMA_VIOLATION`

### Requirement: 读取路径 MUST 兼容历史脏数据
系统 MUST 允许旧历史中不合规行被过滤，不得导致整体读取失败。

#### Scenario: history 存在脏数据
- **WHEN** `/events/history` 读取到旧版不合规事件
- **THEN** 系统跳过该事件并继续返回其余合法事件

### Requirement: 内部桥接校验失败 MUST 记录诊断并降级
系统 MUST 在内部桥接对象不合规时记录 `diagnostic.warning`，并使用最小安全回退。

#### Scenario: pending_interaction 内部不合法
- **WHEN** 内部推断的 pending payload 缺失关键字段
- **THEN** 系统记录 `SCHEMA_INTERNAL_INVALID`
- **AND** 使用最小可用 pending 继续流程
