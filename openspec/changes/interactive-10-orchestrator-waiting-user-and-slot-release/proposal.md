## Why

即使有了交互 API，如果 orchestrator 仍按“一次 run 持有并发槽位直到终态”的模型运行，  
那么在 `waiting_user` 阶段会长期占用执行资源，吞吐量会显著下降，也无法满足可恢复引擎的“等待期间释放槽位”目标。

但该策略仅适用于支持 resume 的引擎。对于不支持 resume 的引擎，仍需允许 interactive，但必须保留后台进程并引入等待超时回收机制。

因此需要把 run 生命周期从“单段执行”升级为“按能力分层的可暂停/可恢复状态机”，并重构并发槽位管理。

## Dependency

- 本 change 依赖 `interactive-05-engine-session-resume-compatibility`。
- 未先完成 `interactive-05` 时，本 change 只可实现状态机骨架，不可落地真实跨进程 resume。

## What Changes

1. 扩展 run 生命周期状态：
   - 新增 `waiting_user`（非终态）。
   - 保留 `queued/running/succeeded/failed/canceled`。

2. 将 orchestrator 改为多回合状态机：
   - 单回合执行后可进入 `waiting_user`；
   - `resumable`：收到 reply 后重新入队并继续下一回合；
   - `sticky_process`：收到 reply 后投递给驻留进程继续下一回合；
   - 直到输出终态结果。

3. 并发槽位策略按档位分支（关键）：
   - `resumable`：run 进入 `waiting_user` 前释放 slot；恢复回合开始前重新申请 slot。
   - `sticky_process`：run 进入 `waiting_user` 后保持 slot，不释放；仅在终态/失败/取消时释放。

4. 交互状态持久化：
   - 持久化当前 pending interaction 与历史回复；
   - `resumable` 支持跨进程恢复；
   - `sticky_process` 记录等待截止时间，超时杀进程并结束任务。

## Impact

- `server/models.py`（RunStatus 扩展）
- `server/services/job_orchestrator.py`
- `server/services/concurrency_manager.py`（调用时序变化）
- `server/services/run_store.py`
- `server/services/workspace_manager.py`（必要时补充交互文件目录）
- `tests/unit/test_job_orchestrator.py`
- `tests/unit/test_concurrency_manager.py`
- `tests/integration/run_integration_tests.py`
