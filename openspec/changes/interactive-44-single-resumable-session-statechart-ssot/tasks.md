## 1. Runtime Semantics Convergence

- [x] 1.1 删除 `EngineInteractiveProfileKind` 与 sticky 错误码常量。
- [x] 1.2 `AgentCliManager.resolve_interactive_profile` 收敛为单档位返回。
- [x] 1.3 `job_orchestrator` 删除 sticky watchdog/slot-hold/process-binding 分支。
- [x] 1.4 `run_interaction_service` reply 统一进入 `queued` 并重新调度。
- [x] 1.5 strict 分流收敛：`strict=true` 不超时失败，`strict=false` 超时自动推进。

## 2. Storage Migration

- [x] 2.1 重建 `request_interactive_runtime` 最小字段结构。
- [x] 2.2 启动期执行一次性兼容迁移（幂等）。
- [x] 2.3 删除 sticky 专属存储 API。

## 3. Statechart SSOT

- [x] 3.1 新增实现侧状态机表 `server/services/session_statechart.py`。
- [x] 3.2 新增状态图文档 `docs/session_runtime_statechart_ssot.md`（Layer A/B/C + 映射附录）。
- [x] 3.3 将 orchestrator 关键分支切换为状态机事件语义。

## 4. Spec and Docs

- [x] 4.1 更新主规格：移除 sticky 双档位语义，统一 strict 行为。
- [x] 4.2 新增主规格 `session-runtime-statechart-ssot`。
- [x] 4.3 更新 `docs/api_reference.md`、`docs/dev_guide.md`、`docs/runtime_stream_protocol.md`。

## 5. Tests

- [x] 5.1 改造现有单测：移除 sticky 分支断言。
- [x] 5.2 新增 `tests/unit/test_session_statechart_contract.py`。
- [x] 5.3 新增 `tests/unit/test_protocol_state_alignment.py`。
- [x] 5.4 运行相关单测并通过。
