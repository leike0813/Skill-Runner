# engine-execution-failfast Specification

## Purpose
定义任务执行的硬超时终止和失败分类（AUTH_REQUIRED/TIMEOUT）策略。
## Requirements
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
系统 MUST 基于已捕获输出进行归类，并将 `failure_reason` 作为终态判定的最高优先级。`AUTH_REQUIRED` 的主来源 MUST 为 `auth_detection` 层，而不是仅靠 `_looks_like_auth_required()`。普通非零退出仅允许在 `auth_detection.confidence=high` 时升级为 `AUTH_REQUIRED`。

#### Scenario: 高置信度 auth detection 触发 AUTH_REQUIRED
- **GIVEN** `auth_detection.confidence=high`
- **WHEN** 输出命中稳定 auth-required 规则
- **THEN** `failure_reason` 必须为 `AUTH_REQUIRED`
- **AND** run 必须进入 `failed`

#### Scenario: 低置信度 detection 不自动升级 AUTH_REQUIRED
- **GIVEN** `auth_detection.confidence=low`
- **WHEN** 输出属于问题样本层并伴随普通非零退出
- **THEN** run 不得自动升级为 `AUTH_REQUIRED`
- **AND** detection 结果必须保留到审计中

### Requirement: 失败归类 MUST 可用于轮询终态判断
系统 MUST 在状态与结果中返回归类后的失败信息，确保客户端能结束轮询并得到失败结果。

#### Scenario: Timeout 后轮询收敛
- **WHEN** run 因 timeout 失败
- **THEN** 轮询接口必须返回 `status=failed`
- **AND** 客户端不会无限轮询 `running`

### Requirement: Timeout 失败任务 MUST 保留调试产物但不得入缓存
系统在 timeout 失败后 MUST 保留已生成的日志与 artifacts 用于排障，但 MUST NOT 记录为可命中的 cache。

#### Scenario: Timeout 后缓存约束
- **WHEN** run 最终因 timeout 失败
- **THEN** cache entry 不得写入
- **AND** 下次相同请求不得命中该 run

#### Scenario: Timeout 后调试文件保留
- **WHEN** timeout 发生前已产生部分日志或 artifacts
- **THEN** 这些文件应保留在 run 目录中供调试查看

### Requirement: Codex refresh-token reauth exits MUST be attributable as AUTH_REQUIRED

当 Codex 因 refresh token 失效族错误而非零退出时，系统 MUST 能基于高置信度 auth signal 将该失败归因为 `AUTH_REQUIRED`，从而复用既有 `waiting_auth` 流程。

#### Scenario: codex refresh-token reauth failure can enter waiting_auth
- **GIVEN** interactive Codex run 的 parser 产出 `confidence=high` 的 `codex_refresh_token_reauth_required`
- **WHEN** 进程以非零退出结束
- **THEN** lifecycle 必须可进入 `waiting_auth`
- **AND** 使用现有 Codex method-selection / auth session 机制

