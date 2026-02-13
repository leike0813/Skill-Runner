## ADDED Requirements

### Requirement: 任务执行 MUST 启用硬超时并终止阻塞子进程
系统 MUST 对 Agent 子进程执行施加硬超时（默认 600s），超时后必须终止子进程并结束任务。

#### Scenario: 子进程超时
- **WHEN** 某 run 的引擎子进程超过硬超时
- **THEN** 系统终止该子进程
- **AND** run 进入 `FAILED` 终态

### Requirement: 系统 MUST 对超时失败进行 AUTH_REQUIRED/TIMEOUT 分类
系统 MUST 基于已捕获输出进行归类：命中鉴权阻塞语义时为 `AUTH_REQUIRED`，否则为 `TIMEOUT`。

#### Scenario: 命中鉴权阻塞语义
- **WHEN** 超时或失败输出包含鉴权阻塞特征文本
- **THEN** 失败原因归类为 `AUTH_REQUIRED`
- **AND** 对 iFlow 至少覆盖 `SERVER_OAUTH2_REQUIRED` 语义（在 managed 配置基线正确时）

#### Scenario: 未命中鉴权语义
- **WHEN** 超时且输出未命中鉴权阻塞特征
- **THEN** 失败原因归类为 `TIMEOUT`

### Requirement: 失败归类 MUST 可用于轮询终态判断
系统 MUST 在状态与结果中返回归类后的失败信息，确保客户端停止无限轮询。

#### Scenario: 鉴权阻塞导致失败
- **WHEN** run 因鉴权阻塞失败
- **THEN** 轮询接口返回 `status=failed`
- **AND** error 信息中包含 `AUTH_REQUIRED` 语义
