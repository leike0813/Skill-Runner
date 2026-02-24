## MODIFIED Requirements

### Requirement: 系统 MUST 基于恢复能力选择 interactive 执行档位
系统 MUST 收敛为单一可恢复会话配置，不再存在 `resumable|sticky_process` 双档位。

#### Scenario: probe 结果不改变单档位策略
- **WHEN** interactive run 创建时执行能力探测
- **THEN** 系统始终写入可恢复会话配置
- **AND** 不产生 sticky 分支

### Requirement: resumable 档位 MUST 在 waiting_user 前持久化会话句柄
系统 MUST 在进入 `waiting_user` 前持久化会话句柄，作为统一恢复前提。

#### Scenario: 句柄缺失时失败
- **WHEN** 需要恢复会话但句柄缺失
- **THEN** run 进入 `failed`
- **AND** `error.code=SESSION_RESUME_FAILED`
