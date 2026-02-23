## ADDED Requirements

### Requirement: Harness MUST 复用项目核心 RASP/FCMP 转译链路
系统 MUST 复用本项目既有运行时协议实现（RASP/FCMP）进行解析与转译，禁止在 harness 内实现并维护另一套语义不一致的核心转译逻辑。

#### Scenario: 转译语义一致
- **WHEN** harness 对同一 run attempt 生成对话事件
- **THEN** 事件协议版本、类型与字段语义与项目核心 RASP/FCMP 实现一致
- **AND** 不因 harness 渲染层引入额外协议分叉

### Requirement: Harness MUST 产出按 attempt 组织的审计工件
系统 MUST 对每次 attempt 产出可追溯审计工件，至少包含 meta、stdin、stdout、stderr、pty-output、fs-before、fs-after、fs-diff。

#### Scenario: 复用 run 时工件不覆盖
- **WHEN** 同一 run 发生多轮 start/resume
- **THEN** 每轮均写入新的 attempt 序号工件
- **AND** 历史工件保持可读取

### Requirement: Harness PTY 录制命令 MUST 兼容 util-linux script 参数规则
系统 MUST 在启用 `--log-out` 等日志参数时构造兼容 util-linux `script` 的命令参数，不得附加导致参数冲突的多余位置参数。

#### Scenario: 开启 --log-out 时不附加额外 typescript 位置参数
- **WHEN** harness 使用 `script` 并传入 `--log-out <path>`
- **THEN** 构造的 `script` 命令不再追加额外的 typescript 位置参数（例如 `/dev/null`）
- **AND** 避免出现 `script: unexpected number of arguments` 错误

### Requirement: Harness MUST 默认不落盘 fd-trace 审计文件
系统 MUST 与当前项目策略保持一致，默认不持久化 `fd-trace.N.log`。

#### Scenario: 审计目录不存在 fd-trace 文件
- **WHEN** harness 运行完成并写入审计工件
- **THEN** `.audit/` 中不存在 `fd-trace.N.log`
- **AND** 其他必要审计工件仍完整可用

### Requirement: Harness MUST 支持 translate 级别输出视图
系统 MUST 提供与 `--translate 0|1|2|3` 对应的输出层级，支持从原始输出到结构化转译视图的分级展示。

#### Scenario: translate 级别驱动不同输出
- **WHEN** 用户分别使用 translate 0/1/2/3 运行同一命令
- **THEN** 输出视图按级别变化
- **AND** 审计原始工件不随展示级别而丢失

#### Scenario: translate=3 输出前端模拟 Markdown 视图
- **WHEN** 用户使用 `--translate 3` 执行 start 或 resume
- **THEN** 终端输出包含标题 `### Simulated Frontend View (Markdown)`
- **AND** 后续内容以 Markdown 列表项展示面向前端消费的对话文本（如 `Assistant:` / `System:`）
- **AND** 一致性报告继续写入 `.audit/conformance-report.N.json`，而非替代为终端主输出

#### Scenario: translate=3 抑制默认英文待输入提示
- **WHEN** FCMP `user.input.required` 使用默认提示 `Provide next user turn`
- **THEN** 前端模拟 Markdown 视图不重复显示该英文提示行
- **AND** 保留本地化占位行 `System: (请输入下一步指令...)`

### Requirement: Harness MUST 提供一致性报告输出
系统 MUST 为每次运行输出可读的一致性报告，报告至少包含 parser profile、关键 FCMP 事件、降级诊断与 completion 结论。

#### Scenario: 报告包含关键一致性字段
- **WHEN** harness 完成一次运行并生成报告
- **THEN** 报告包含 parser profile、FCMP 事件摘要、diagnostics、completion state
- **AND** 报告可用于与参考实现结果逐项对照

### Requirement: RASP 原始证据保留 MUST 与 FCMP 去重解耦
系统 MUST 在 RASP 层保留原始证据；任何重复抑制或噪声压缩 MUST 仅作用于 FCMP 展示层，不得改写 RASP 原始记录。

#### Scenario: FCMP 抑制不影响 RASP 证据
- **WHEN** 转译层对重复 raw 内容执行抑制
- **THEN** FCMP 输出可减少重复噪声
- **AND** RASP 原始记录仍可完整回溯

### Requirement: Gemini 解析 MUST 支持多行 JSON 文档并遵循 split 优先策略
系统 MUST 支持对 Gemini 输出中的多行 JSON 文档进行结构化解析，并在 split 流与 PTY 同时可用时优先消费 split 流。

#### Scenario: stdout 多行 JSON 仍可提取 response
- **WHEN** Gemini 在 `stdout` 输出带噪声前缀的多行 JSON 文档（包含 `session_id` 与 `response`）
- **THEN** 解析器提取 `session_id` 和 `assistant message`
- **AND** 不退化为仅 `raw.stdout` 事件

#### Scenario: split 与 PTY 重复载荷时不重复消费 PTY
- **WHEN** `stdout` 与 `pty-output` 同时包含同一结构化 Gemini 响应
- **THEN** 解析器优先消费 split 流结构化结果
- **AND** 不因重复消费 PTY 产生冗余 raw 事件
