## ADDED Requirements

### Requirement: 前端 MUST 仅消费统一对话消息协议（FCMP）
系统 MUST 提供 `fcmp/1.0` 作为前端对话层唯一稳定消费面，前端不得直接解析引擎原始输出格式。

#### Scenario: 前端接收统一消息信封
- **WHEN** 前端订阅运行中的对话消息
- **THEN** 服务端返回 `protocol_version=fcmp/1.0` 的消息信封
- **AND** 消息包含 `run_id`、`seq`、`type`、`data`

### Requirement: FCMP 消息序列 MUST 保证有序且终态互斥
系统 MUST 保证同一 run 下 `seq` 单调递增，并保证 `conversation.completed` 与 `conversation.failed` 互斥。

#### Scenario: 正常完成
- **WHEN** 运行判定为完成
- **THEN** 系统发送 `conversation.completed`
- **AND** 不再发送 `conversation.failed`

#### Scenario: 运行失败
- **WHEN** 运行判定为失败或中断
- **THEN** 系统发送 `conversation.failed`
- **AND** 不再发送 `conversation.completed`

### Requirement: 系统 MUST 定义从 RASP 到 FCMP 的标准转译映射
系统 MUST 将运行时事件按固定映射转译为前端事件，至少支持 `conversation.started`、`assistant.message.final`、`user.input.required`、`diagnostic.warning`。

#### Scenario: 会话建立映射
- **WHEN** RASP 中首次出现可用会话标识
- **THEN** 转译器发送 `conversation.started`
- **AND** 在消息中回填 `session_id`

#### Scenario: 主回复映射
- **WHEN** RASP 事件类型为 `agent.message.final`
- **THEN** 转译器发送 `assistant.message.final`
- **AND** 文本内容映射到 `data.text`

### Requirement: 转译器 MUST 在 FCMP 层抑制 raw 回显噪声且保持可追踪
系统 MUST 保留 RASP 原始事件用于审计与回放，但在 RASP->FCMP 转译中对“与 assistant 主消息重复的 raw 回显块”执行规范化抑制，避免对话流被噪声淹没。

#### Scenario: 抑制 raw 回显重复块
- **WHEN** raw 事件与 `assistant.message.final` 按行比对出现同流向连续重复块
- **THEN** 转译器抑制该重复 raw 块进入 FCMP 主事件流
- **AND** 仅抑制连续长度达到阈值（默认 `>=3` 行）的重复块以降低误杀

#### Scenario: 抑制行为可审计
- **WHEN** 转译器发生 raw 回显抑制
- **THEN** 系统发送 `diagnostic.warning`
- **AND** 诊断码为 `RAW_DUPLICATE_SUPPRESSED`
- **AND** 诊断中包含 `suppressed_count`

#### Scenario: 非重复 raw 不得被误抑制
- **WHEN** raw 事件不构成与主回复的重复回显块
- **THEN** 该 raw 事件可继续转译为 `raw.stdout` 或 `raw.stderr`
- **AND** 不得因启用抑制而丢失非重复排障信息

### Requirement: user.input.required MUST 采用硬规则判定
系统 MUST 按 done marker 与引擎终止信号进行硬判定，不得使用语义猜测决定是否进入等待用户输入。

#### Scenario: 已完成时不得要求用户输入
- **WHEN** 判定链路已命中 done marker
- **THEN** 系统发送 `conversation.completed`
- **AND** 不发送 `user.input.required`

#### Scenario: 结束信号无 done marker
- **WHEN** 命中终止信号且未命中 done marker
- **THEN** 系统发送 `user.input.required`
- **AND** 同步发送 `diagnostic.warning` 表示缺失完成标记
