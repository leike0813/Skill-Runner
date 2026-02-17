## Why

当前服务没有对前端开放“终止某个 Job”的标准 API，客户端只能被动等待超时或失败。  
在 interactive + SSE 改造后，Run 管理页需要用户主动中止任务，这个能力必须先补齐。

## What Changes

1. 新增可由前端直接调用的 Job 终止接口：
   - `POST /v1/jobs/{request_id}/cancel`
   - `POST /v1/temp-skill-runs/{request_id}/cancel`
2. 为运行中任务建立可控终止通道（向对应 CLI 进程发送终止信号并回收）。
3. 终止语义标准化：
   - 仅 `queued/running/waiting_user` 可被终止；
   - 终态请求幂等返回，不重复执行终止动作；
   - 终止成功后状态统一为 `canceled`，并记录 `CANCELED_BY_USER` 错误码。
4. 与可观测能力对齐：
   - 终止后状态接口、日志接口、SSE 事件流均能观测到 `canceled` 终态与取消原因。
5. 为后续统一管理接口（interactive-27）与 Web 迁移（interactive-28）提供底层终止原语。

## Capabilities

### New Capabilities
- `interactive-job-cancel-api`: 定义 Job 终止接口、幂等行为、错误码与返回契约。
- `interactive-run-cancel-lifecycle`: 定义 queued/running/waiting_user 三种状态下的终止执行路径与资源回收要求。

### Modified Capabilities
- `interactive-log-sse-api`: 增加取消终态事件语义，确保客户端实时收到 `canceled` 结束信号。

## Impact

- `server/routers/jobs.py`
- `server/routers/temp_skill_runs.py`
- `server/services/job_orchestrator.py`
- `server/adapters/base.py`
- `server/services/run_store.py`
- `server/services/concurrency_manager.py`（如需可取消排队）
- `server/services/run_observability.py`
- `server/models.py`
- `docs/api_reference.md`
- `docs/dev_guide.md`
- `tests/unit/test_v1_routes.py`
- `tests/unit/test_job_orchestrator.py`
- `tests/unit/test_run_observability.py`
- `tests/integration/run_integration_tests.py`
- `tests/e2e/run_container_e2e_tests.py`
