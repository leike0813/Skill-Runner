## ADDED Requirements

### Requirement: Adapter MUST 通过统一进程治理注册并释放 run attempt 进程
运行时 adapter 在创建引擎子进程后 MUST 注册 lease，并在任意退出路径 release；取消执行 MUST 通过统一终止器。

#### Scenario: 正常完成释放 lease
- **WHEN** run attempt 正常结束
- **THEN** 对应 lease 状态变为 closed

#### Scenario: 取消执行统一终止
- **WHEN** 收到取消请求
- **THEN** adapter 使用统一终止器处理进程树
- **AND** lease 最终关闭
