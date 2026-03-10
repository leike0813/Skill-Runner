## ADDED Requirements

### Requirement: Attempt audit skeleton MUST include io_chunks file
attempt 审计骨架 MUST 预创建 `.audit/io_chunks.<attempt>.jsonl`，作为 chunk 级真相源。

#### Scenario: initialize attempt audit skeleton
- **WHEN** orchestration 初始化 attempt 审计骨架
- **THEN** `.audit/io_chunks.<attempt>.jsonl` MUST 已存在
- **AND** 不替代既有 `stdout/stderr` 明文日志文件

### Requirement: Protocol rebuild MUST backup audit files before overwrite
手动重构协议 MUST 在覆盖写回前备份当前审计协议文件。

#### Scenario: rebuild protocol for a run
- **WHEN** 管理端触发 run 协议重构
- **THEN** 系统 MUST 将待覆盖的协议文件备份到 `.audit/rebuild_backups/<timestamp>/attempt-<N>/`
- **AND** 重构失败时原审计文件仍可从备份恢复
