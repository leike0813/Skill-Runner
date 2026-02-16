## Context

当前 interactive 链路已经引入 `sticky_process` 与 `resumable` 两种执行档位。  
其中 `sticky_process` 依赖 hard timeout 完成等待超时回收，但 timeout 命名和消费边界在前序 change 中存在演进痕迹，容易产生“配置值与实际行为不一致”的风险。

## Goals

1. 将会话 hard timeout 统一收敛到单一配置键：`session_timeout_sec`。
2. 统一所有消费点使用同一“归一化 timeout 值”。
3. 保证默认值一致（`1200` 秒）且可覆盖。
4. 为历史命名提供受控兼容与可观测的迁移路径。
5. 作为会话超时键名与兼容策略的唯一 owner change，供前序/后续 change 消费。

## Non-Goals

1. 不调整 interactive 状态机本身。
2. 不改变错误码语义（`INTERACTION_WAIT_TIMEOUT` 等保持不变）。
3. 不在本 change 引入新的执行模式。

## Design

### 1) 配置模型统一

- 引入单一配置键：`session_timeout_sec`。
- 默认值：`1200`。
- 约束：值必须为正整数，且有最小值保护（例如 >= 1）。

### 2) 归一化解析规则

新增统一解析函数（示意：`resolve_session_timeout()`）：
1. 若显式提供 `session_timeout_sec`，直接使用。
2. 若仅提供历史键（如 `interactive_wait_timeout_sec` / `hard_wait_timeout_sec`），映射为 `session_timeout_sec` 并记录 deprecation。
3. 若同时提供新旧键，`session_timeout_sec` 优先，旧键忽略并告警。
4. 若均未提供，使用默认值 `1200`。

### 3) 消费位点重构

所有 hard timeout 消费位点必须使用统一归一化值，不得直接读旧键或硬编码常量：
- Orchestrator：计算 `wait_deadline_at`；
- 进程管理：等待超时终止逻辑；
- 持久化：记录 run 级 effective timeout；
- 可观测：返回/日志中可查询当前 effective timeout（用于排障）。

### 4) 迁移与回滚边界

- 本阶段保留历史键兼容读取（有限期），确保已有部署不立即中断。
- 文档对外仅公开 `session_timeout_sec`。
- 若出现紧急回滚，兼容读取可以保证旧配置仍能生效。

## Risks & Mitigations

1. **风险：旧配置在多处残留，导致部分路径不生效**
   - 缓解：通过统一解析函数收口，禁止模块直接读取原始键名。
2. **风险：默认值变更引发行为漂移**
   - 缓解：以测试固定默认值 `1200`，并在 API 文档明确说明。
3. **风险：迁移期冲突键导致误解**
   - 缓解：明确优先级 + 统一 deprecation 日志输出。
