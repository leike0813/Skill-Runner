## Why

在 interactive 相关 change 的推进过程中，hard timeout 的命名与消费位置出现了多版本演进痕迹（如 `interactive_wait_timeout_sec`、`wait_timeout_sec`、固定常量等）。  
如果不统一，会带来以下问题：

1. 配置面向用户的认知成本高，难以判断“到底哪个字段生效”。
2. 不同模块可能消费不同名称，导致超时行为不一致。
3. 后续 verify/observe 时无法稳定定位“实际生效值”。

因此需要在 `interactive-10` 之后新增一个专门的配置重构 change，统一 hard timeout 配置与消费链路。

## Dependency

- 本 change 依赖 `interactive-05-engine-session-resume-compatibility` 对“会话超时语义”的基础引入。
- 本 change 依赖 `interactive-10-orchestrator-waiting-user-and-slot-release`。
- 本 change 产出的统一配置语义应被后续 change 复用，避免继续引入新命名。

## What Changes

1. 统一 timeout 配置命名：
   - 会话级 hard timeout 统一为 `session_timeout_sec`；
   - 默认值统一为 `1200` 秒。

2. 统一 timeout 配置消费位置：
   - `sticky_process` 的 `wait_deadline_at` 计算统一使用 `session_timeout_sec`；
   - 等待超时回收与错误映射统一使用同一值；
   - 运行时可观测字段记录“effective session timeout”。

3. 清理历史命名并给出迁移策略：
   - 移除交互专用 timeout 命名在新增设计中的继续扩散；
   - 对历史命名提供有限兼容映射（如存在），并在日志中输出 deprecation 提示；
   - 明确冲突优先级：`session_timeout_sec` 优先。

4. 文档与测试同步：
   - 文档仅保留 `session_timeout_sec`；
   - 单测/集成测试覆盖默认值、覆盖值、兼容映射与冲突优先级。

## Impact

- `server/config/settings.py`（或等价配置定义位置）
- `server/services/job_orchestrator.py`
- `server/services/agent_cli_manager.py`
- `server/services/run_store.py`
- `server/services/run_observability.py`
- `docs/api_reference.md`
- `docs/dev_guide.md`
- `tests/unit/test_job_orchestrator.py`
- `tests/unit/test_config*.py`
- `tests/integration/run_integration_tests.py`
