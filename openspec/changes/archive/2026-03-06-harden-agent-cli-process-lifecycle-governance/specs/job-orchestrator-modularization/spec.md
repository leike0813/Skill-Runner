## ADDED Requirements

### Requirement: 启动恢复 MUST 先处理受管 orphan 进程
编排器在执行不完整 run 恢复前，MUST 先执行受管 lease 进程的 orphan 清理，并将结果写入恢复日志。

#### Scenario: 启动顺序约束
- **WHEN** 服务启动进入 runtime 恢复阶段
- **THEN** 系统先执行受管 orphan lease reap
- **AND** 再执行 run 恢复
