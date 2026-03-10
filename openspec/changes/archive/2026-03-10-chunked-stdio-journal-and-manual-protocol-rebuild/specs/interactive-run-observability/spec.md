## ADDED Requirements

### Requirement: Protocol rebuild MUST be manual-only operation
协议重构 MUST 仅由人工触发，不得在页面访问或常规历史查询时自动执行。

#### Scenario: regular run detail load
- **WHEN** 用户仅打开 run detail 页面并读取协议历史
- **THEN** 系统 MUST 直接回放现有审计文件
- **AND** MUST NOT 自动触发重构

### Requirement: Rebuild engine MUST run in strict replay single-path
手动重构时，系统 MUST 仅按 strict replay 单路径执行，不允许 best-effort 回退路径。

#### Scenario: strict replay evidence complete
- **WHEN** attempt 存在有效 `io_chunks.<N>.jsonl`、`orchestrator_events.<N>.jsonl`、`meta.<N>.json`
- **THEN** 重构 MUST 使用这些证据按真实 live 链路回放

#### Scenario: strict replay evidence missing
- **WHEN** 任一关键证据缺失或损坏
- **THEN** 该 attempt MUST 失败
- **AND** MUST NOT 覆写该 attempt 审计文件

### Requirement: Rebuild MUST run in strict_replay mode
手动重构 MUST 固定为 strict_replay 口径，不允许 canonical / forensic best-effort 分支。

#### Scenario: rebuild request accepted
- **WHEN** 调用重构接口成功触发
- **THEN** 系统 MUST 以 strict replay 口径重建 RASP/FCMP
- **AND** 返回结果中 MUST 显示 `mode=strict_replay`

### Requirement: Rebuild MUST NOT inject compensation events
重构期间系统 MUST NOT 注入补偿事件；系统 MUST 仅写入真实回放链路自然产出的事件。

#### Scenario: waiting-user without replay evidence
- **WHEN** 回放未自然产出 `interaction.user_input.required`
- **THEN** 系统 MUST 保持缺失
- **AND** MUST NOT 通过 meta 注入该事件
