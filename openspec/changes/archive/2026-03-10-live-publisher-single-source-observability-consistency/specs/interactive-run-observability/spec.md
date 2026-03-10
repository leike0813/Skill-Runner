## ADDED Requirements

### Requirement: FCMP/RASP protocol history MUST NOT trigger query-time rematerialization
`protocol/history` 的 FCMP/RASP 查询 MUST 不再在查询路径重建并覆盖审计事件文件。

#### Scenario: fetch protocol history for running run
- **GIVEN** run 正在运行
- **WHEN** 客户端请求 `protocol/history`（`stream=fcmp|rasp`）
- **THEN** 服务 MUST 仅消费 live journal 与已有 audit 镜像
- **AND** MUST NOT 在该查询路径调用 stdout/stderr 重算写盘。

### Requirement: terminal FCMP/RASP history MUST flush mirror before audit-only read
run 进入 terminal 后，服务 MUST 在读取 audit-only 历史前完成 live mirror drain。

#### Scenario: terminal transition with pending mirror writes
- **GIVEN** run 已进入 terminal，且镜像落盘任务仍在进行
- **WHEN** 客户端请求 `protocol/history`（`stream=fcmp|rasp`）
- **THEN** 服务 MUST 先等待 mirror flush 完成
- **AND** 再返回 audit-only 结果。
