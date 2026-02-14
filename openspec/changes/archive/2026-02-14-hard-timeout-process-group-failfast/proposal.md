## Why

在实际部署中，Hard Timeout 触发后出现了与预期不一致的行为：

- 客户端长时间轮询，未及时收到失败终态；
- 后台 Agent 进程在超时后仍继续执行；
- 个别场景出现“超时后最终有成功输出”的状态竞争，导致终态与结果不一致。

根因是当前超时终止链路只覆盖父进程，未强约束子进程组回收；同时终态判定没有将 `failure_reason=TIMEOUT` 设为绝对失败优先。

## What Changes

- 引入“进程组级别终止”策略，确保 timeout 后整个 Agent 进程树被回收。
- 将 `failure_reason` 设为终态最高优先级：
  - `TIMEOUT` / `AUTH_REQUIRED` 一旦出现，run 必须失败，不再受 `exit_code` 或输出 JSON 反向覆盖。
- 保留 timeout 期间已产生的日志与 artifacts 用于调试，但 timeout run 不得写入 cache。
- 增加对应测试覆盖，防止回归。

## Impact

- 受影响模块：
  - `server/adapters/base.py`
  - `server/adapters/codex_adapter.py`
  - `server/adapters/gemini_adapter.py`
  - `server/adapters/iflow_adapter.py`
  - `server/services/job_orchestrator.py`
- 受影响测试：
  - `tests/unit/test_adapter_failfast.py`
  - `tests/unit/test_job_orchestrator.py`
