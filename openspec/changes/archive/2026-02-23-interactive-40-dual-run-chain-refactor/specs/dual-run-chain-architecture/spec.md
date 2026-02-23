## ADDED Requirements

### Requirement: Dual-run execution MUST separate source-specific responsibilities from shared core
系统 MUST 在执行架构层显式区分 source 专属职责与共用职责，以支持双链路长期演进。

#### Scenario: Source-specific responsibilities remain isolated
- **WHEN** 请求来源为 `installed` 或 `temp`
- **THEN** skill 获取方式、source 生命周期管理、存储命名空间与 source 扩展因子由 source adapter 独立处理
- **AND** 这些职责不得散落在通用执行核心中

#### Scenario: Shared execution stages are centralized
- **WHEN** 请求进入 create/upload/start/read/cancel 通用阶段
- **THEN** runtime/model/mode 校验、调度、缓存策略、错误映射、run 读取框架 MUST 走统一核心服务
- **AND** 双链路不得各自维护重复实现

### Requirement: Run source capability matrix MUST be explicit and parity-constrained
系统 MUST 为不同 source 提供能力矩阵，并在路由/服务层按能力矩阵判定可用行为。  
对于 `pending/reply/history/range`，installed 与 temp 的能力位 MUST 保持一致（同为可用）。

#### Scenario: Parity-constrained capability matrix
- **WHEN** 系统定义 source capability matrix
- **THEN** `supports_pending_reply`、`supports_event_history`、`supports_log_range` 在 installed 与 temp 上必须同值
- **AND** 该同值在本变更中必须为 `true`

#### Scenario: Capability behavior is consistent across sources
- **WHEN** 客户端针对 installed 或 temp run 请求 pending/reply/history/range
- **THEN** 系统返回同等可用能力
- **AND** 状态约束、参数校验与错误语义保持一致

### Requirement: Cache policy MUST be shared while cache namespace remains source-isolated
缓存策略（例如 auto-only）MUST 统一；缓存存储命名空间 MUST 按 source 隔离。

#### Scenario: Shared cache policy
- **WHEN** 任一 source 的 run 提交执行
- **THEN** cache enable/disable 判定逻辑遵循同一策略实现

#### Scenario: Source-isolated cache namespace
- **WHEN** 不同 source 产生相同 cache key 字符串
- **THEN** 两者缓存读取/写入仍在各自 namespace 内执行
- **AND** 不允许跨 source 缓存命中

### Requirement: External API contracts MUST remain backward-compatible during refactor
本次重构 MUST 保持现有双链路外部 API 路径与基础语义兼容。

#### Scenario: API compatibility
- **WHEN** 现有客户端继续调用 `/v1/jobs*` 与 `/v1/temp-skill-runs*`
- **THEN** 调用路径与主流程语义保持兼容
- **AND** 重构仅影响内部实现组织方式
