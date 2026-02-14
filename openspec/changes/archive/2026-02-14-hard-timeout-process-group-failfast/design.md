## Context

本变更只聚焦 timeout fail-fast 正确性，不改变 API 形态与缓存键策略。

关键目标：

1. timeout 触发后快速收敛为 failed；
2. 进程树必须被回收，避免“父进程死、子进程活”；
3. 失败优先级稳定，避免 `exit_code=0` 覆盖 timeout 失败。

## Decisions

### 1) 进程组级别终止

- 子进程启动时按平台启用进程组隔离：
  - Unix: `start_new_session=True`
  - Windows: `CREATE_NEW_PROCESS_GROUP`
- timeout 后按“温和 -> 强制”两阶段终止整个进程组：
  - 先 TERM/CTRL_BREAK；
  - 超过短等待后再 KILL。
- 读流任务采用有界收尾，避免无限等待 EOF。

### 2) 终态判定优先级

在 `JobOrchestrator` 中固定优先级：

1. 若 `failure_reason in {TIMEOUT, AUTH_REQUIRED}` -> `failed`
2. 否则按现有 `exit_code + output schema` 判定

该规则防止 timeout 后出现“最终 success”覆盖。

### 3) Timeout 调试数据保留与缓存约束

- timeout run 保留当前已落盘的：
  - `logs/stdout.txt`
  - `logs/stderr.txt`
  - `artifacts/**`
  - `result/result.json`（failed envelope）
- timeout run 不写 cache entry。

## Test Strategy

- `test_adapter_failfast.py`：
  - 覆盖 timeout 后返回 TIMEOUT；
  - 覆盖 timeout 路径可及时返回（不挂死）。
- `test_job_orchestrator.py`：
  - 覆盖 `failure_reason=TIMEOUT + exit_code=0` 仍 failed；
  - 覆盖 timeout 场景不入 cache；
  - 覆盖 timeout 场景 artifacts 仍被保留在结果中。
