## ADDED Requirements

### Requirement: 系统 MUST 产出统一运行时事件协议（RASP）
系统 MUST 将运行中的引擎输出归一化为 `rasp/1.0` 事件信封后再分发，事件至少包含协议版本、run 标识、单调递增序号、事件分类与原始日志引用。

#### Scenario: 运行事件使用统一信封
- **WHEN** 任一引擎运行中产生可观测输出
- **THEN** 系统产出 `protocol_version=rasp/1.0` 的事件对象
- **AND** 事件包含 `run_id`、`seq`、`event.category`、`event.type`
- **AND** 事件包含 `attempt_number` 与 `raw_ref` 用于回溯 stdout/stderr 区间

### Requirement: 系统 MUST 统一 seq/cursor/attempt 语义
系统 MUST 在同一 run 内使用全局单调递增的 `seq`，并定义 `cursor` 与 `attempt_number` 的一致规则，避免 interactive 与 auto 模式混淆。

#### Scenario: interactive 模式 attempt 递增
- **WHEN** interactive run 创建后进入首次执行与后续用户 reply 回合
- **THEN** 初始请求回合 `attempt_number=1`
- **AND** 每次用户 reply 触发的新回合 `attempt_number` 递增 1

#### Scenario: auto 模式 attempt 固定
- **WHEN** run 以 `auto` 模式执行
- **THEN** `attempt_number` 固定为 `1`

#### Scenario: cursor 与 seq 对齐
- **WHEN** 客户端使用 `cursor` 重连事件流
- **THEN** 服务端从 `cursor` 对应的下一个 `seq` 继续发送
- **AND** 同一 `run_id` 下不重复发送已消费事件

### Requirement: 系统 MUST 规范 raw_ref 字段
系统 MUST 为可追溯事件提供一致的 `raw_ref`，至少包含流来源、attempt 与字节区间，确保结构化事件可回跳原始日志。

#### Scenario: raw_ref 最小字段齐备
- **WHEN** 系统产出可追溯的结构化事件
- **THEN** `raw_ref` 至少包含 `attempt_number`、`stream`、`byte_from`、`byte_to`
- **AND** `raw_ref.encoding` 固定为 `utf-8`

### Requirement: 系统 MUST 使用固定事件分类并保持可扩展
系统 MUST 使用标准分类表达运行语义，至少覆盖 `lifecycle`、`agent`、`interaction`、`tool`、`artifact`、`diagnostic`、`raw`。

#### Scenario: 引擎消息映射到 agent 类别
- **WHEN** 解析器识别到引擎的主回复消息
- **THEN** 系统产出 `event.category=agent`
- **AND** `event.type` 为 `agent.message.delta` 或 `agent.message.final`

#### Scenario: 未解析内容映射到 raw 类别
- **WHEN** 引擎输出无法被结构化解析
- **THEN** 系统产出 `event.category=raw`
- **AND** 保留原始文本片段
- **AND** 同时产出 `diagnostic` 事件标记降级原因

### Requirement: RASP 原始事件 MUST 完整保留并与 FCMP 视图解耦
系统 MUST 在 RASP 层完整保留 `raw` 事件用于审计和回放；任何面向对话视图的去重或噪声抑制 MUST 仅发生在 RASP->FCMP 转译层，不得回写或删除 RASP 原始记录。

#### Scenario: RASP 保留 raw 完整性
- **WHEN** 解析器产出 `raw` 类事件
- **THEN** 事件写入 RASP 事件流与落盘工件
- **AND** 可被历史回放接口按 `seq` 或时间区间检索

#### Scenario: FCMP 抑制不影响 RASP 审计
- **WHEN** 转译层对重复 raw 回显执行抑制
- **THEN** 被抑制内容仍保留在 RASP 记录中
- **AND** 审计回放与证据重建结果不受影响

### Requirement: 系统 MUST 定义按引擎 parser profile 的解析策略
系统 MUST 支持并声明解析 profile：`codex_ndjson`、`gemini_json`、`iflow_text`、`opencode_ndjson`，并在事件中记录解析来源与置信度。

#### Scenario: 事件包含 parser profile 与置信度
- **WHEN** 任一 profile 成功或部分成功解析事件
- **THEN** 事件 `source.parser` 为对应 profile 名称
- **AND** 事件 `source.confidence` 为 `[0,1]` 闭区间数值

#### Scenario: profile 漂移时不丢失数据
- **WHEN** 引擎输出字段漂移导致 profile 规则未命中
- **THEN** 系统降级输出 `raw` 事件
- **AND** 产出 `diagnostic.parser.warning`
- **AND** 不丢弃原始日志内容

### Requirement: 系统 MUST 具备确定性的解析容错链路
系统 MUST 在结构化解析失败时按固定顺序执行容错步骤，确保四引擎行为一致且可回归测试。

#### Scenario: NDJSON 行级容错
- **WHEN** `codex_ndjson` 或 `opencode_ndjson` 遇到单行 JSON 解码失败
- **THEN** 该行降级为 `raw` 事件
- **AND** 解析器继续处理后续行
- **AND** 产出 `diagnostic` 告警码标记行级失败

#### Scenario: Gemini 响应容错
- **WHEN** `gemini_json` 的主结构化对象解析失败
- **THEN** 解析器尝试从 `response` 文本中提取 fenced JSON 或可解析 JSON 片段
- **AND** 若仍失败则降级为 `raw` 事件并保留诊断

#### Scenario: iFlow 文本容错
- **WHEN** `iflow_text` 无法提取结构块
- **THEN** 解析器保留原文为 `agent` 或 `raw` 事件
- **AND** 标注低置信度并附诊断事件

### Requirement: 系统 MUST 维护会话关联信息
系统 MUST 在可提取时将会话标识写入事件关联字段，以支持 interactive resume 与跨回合追踪。

#### Scenario: 提取到 session/thread 标识
- **WHEN** 解析器从输出中识别 `thread_id/session_id/session-id/sessionID`
- **THEN** 系统在 `correlation.session_id` 中写入统一会话标识
- **AND** 该会话标识可被后续回复回合复用

### Requirement: 系统 MUST 暴露解析与转译核心指标
系统 MUST 提供运行时协议链路的关键指标，至少覆盖解析命中、降级和不确定终态。

#### Scenario: 记录解析命中与降级指标
- **WHEN** 运行完成或回合结束
- **THEN** 系统记录 parser 命中率与 fallback 计数
- **AND** 指标可按引擎和 profile 维度聚合

#### Scenario: 记录 unknown 终态指标
- **WHEN** completion 判定结果为 `unknown`
- **THEN** 系统记录 unknown 终态计数
- **AND** 指标中可关联 `reason_code` 或诊断码
