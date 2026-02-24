# runtime-event-command-schema Specification

## Purpose
定义运行时核心事件/命令的 JSON Schema 合同与校验策略。

## Requirements

### Requirement: 系统 MUST 维护单一协议 Schema SSOT
系统 MUST 维护覆盖 FCMP/RASP/orchestrator/pending/history/resume-command 的统一 schema 文档。

#### Scenario: 单一真源
- **WHEN** 审查协议对象定义
- **THEN** 存在单一 schema 文件作为 SSOT

### Requirement: 写入路径 MUST 严格校验
系统 MUST 在协议对象落盘/输出前执行 schema 校验。

#### Scenario: 不合法事件写入
- **WHEN** 协议对象不满足 schema
- **THEN** 写入被拒绝并返回 `PROTOCOL_SCHEMA_VIOLATION`

### Requirement: 读取路径 MUST 兼容历史脏数据
系统 MUST 在读取历史对象时过滤不合规行，不中断整体读取。

#### Scenario: history 存在脏数据
- **WHEN** 历史文件中有不合规协议对象
- **THEN** 系统跳过不合规行并返回其余合法行

### Requirement: 内部桥接失败 MUST 记录诊断并降级
系统 MUST 在内部桥接对象校验失败时记录 `SCHEMA_INTERNAL_INVALID` 并使用最小安全回退。

#### Scenario: pending 结构异常
- **WHEN** 内部生成的 pending payload 不合法
- **THEN** 系统记录诊断 warning
- **AND** 回退到最小可用 pending 继续执行

### Requirement: Schema 合法性 MUST 接受语义不变量测试约束
系统 MUST 将“schema 合法”与“语义合法”分层校验，并由不变量测试覆盖语义层。

#### Scenario: schema 通过但映射漂移
- **WHEN** 事件 payload 满足 schema
- **AND** FCMP 状态映射不满足不变量合同
- **THEN** 属性/模型测试失败
