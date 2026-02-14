## MODIFIED Requirements

### Requirement: 任务执行 MUST 启用硬超时并终止阻塞子进程
系统 MUST 对 Agent 子进程执行施加硬超时，超时后必须终止整个相关进程树并结束任务。

#### Scenario: 进程组超时终止
- **WHEN** 某 run 的引擎进程超过硬超时
- **THEN** 系统必须终止该进程及其子进程
- **AND** run 必须进入 `FAILED` 终态

#### Scenario: 终止后读流收敛
- **WHEN** 系统已触发 timeout 终止
- **THEN** 日志读流任务应在有界时间内收敛
- **AND** 任务状态不应长期停留在 `running`

### Requirement: 系统 MUST 对超时失败进行 AUTH_REQUIRED/TIMEOUT 分类
系统 MUST 基于已捕获输出进行归类，并将 `failure_reason` 作为终态判定的最高优先级。

#### Scenario: TIMEOUT 优先失败
- **WHEN** `failure_reason=TIMEOUT`
- **THEN** 无论 `exit_code` 或输出 JSON 是否看似成功，run 都必须为 `failed`

#### Scenario: AUTH_REQUIRED 优先失败
- **WHEN** `failure_reason=AUTH_REQUIRED`
- **THEN** run 必须为 `failed`
- **AND** 错误信息包含鉴权语义

### Requirement: 失败归类 MUST 可用于轮询终态判断
系统 MUST 在状态与结果中返回归类后的失败信息，确保客户端能结束轮询并得到失败结果。

#### Scenario: Timeout 后轮询收敛
- **WHEN** run 因 timeout 失败
- **THEN** 轮询接口必须返回 `status=failed`
- **AND** 客户端不会无限轮询 `running`

## ADDED Requirements

### Requirement: Timeout 失败任务 MUST 保留调试产物但不得入缓存
系统在 timeout 失败后 MUST 保留已生成的日志与 artifacts 用于排障，但 MUST NOT 记录为可命中的 cache。

#### Scenario: Timeout 后缓存约束
- **WHEN** run 最终因 timeout 失败
- **THEN** cache entry 不得写入
- **AND** 下次相同请求不得命中该 run

#### Scenario: Timeout 后调试文件保留
- **WHEN** timeout 发生前已产生部分日志或 artifacts
- **THEN** 这些文件应保留在 run 目录中供调试查看
