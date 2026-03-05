## ADDED Requirements

### Requirement: Run audit MUST include full-lifecycle service log mirror file

每个 run 的 `.audit` MUST 包含 `service.run.log` 作为服务日志全集镜像，覆盖该 run 生命周期内 attempt 内外编排日志。

#### Scenario: run audit pre-creates run-scope service log
- **WHEN** orchestration 完成 run 目录初始化
- **THEN** `.audit/service.run.log` MUST 存在
- **AND** 后续日志追加 MUST 使用该文件作为 run 全集镜像

### Requirement: Attempt audit MUST include service-process log mirror files

每个 run attempt 的 `.audit` 骨架 MUST 包含 `service.<attempt>.log`，用于保存该 run 的服务进程日志镜像。

#### Scenario: attempt audit skeleton pre-creates service log file
- **WHEN** orchestration 初始化 attempt N 的审计骨架
- **THEN** `.audit/service.N.log` MUST 被创建
- **AND** 该文件可在 attempt 执行过程中持续追加

### Requirement: Service log mirror MUST remain run-scoped and history-only

服务日志镜像 MUST 仅包含匹配当前 `run_id`（attempt 分片默认同时匹配 `attempt_number`）的服务日志记录，并且仅作为审计历史，不作为运行状态真相源。

#### Scenario: unscoped logs are excluded from run audit mirror
- **WHEN** 服务日志记录缺失 `run_id` 上下文或 `run_id` 不匹配
- **THEN** 该记录 MUST NOT 写入 `.audit/service.run.log` 或 `.audit/service.<attempt>.log`

#### Scenario: attempt log is subset of run full log
- **GIVEN** run 同时开启 run-scope 与 attempt-scope 镜像
- **WHEN** attempt N 执行期间产生服务日志记录
- **THEN** 记录 MUST 出现在 `.audit/service.run.log`
- **AND** 若记录匹配 attempt N，MUST 同时出现在 `.audit/service.N.log`
