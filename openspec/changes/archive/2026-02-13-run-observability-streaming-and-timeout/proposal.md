## Why

当前 Run 观测存在三个关键短板：

- stdout/stderr 仅在进程结束后落盘，无法实时定位执行卡点；
- 硬超时默认值偏小，且需要明确为可配置策略；
- UI 缺少 run 级观测入口，无法按 request_id 关联 run 目录进行在线诊断。

这些问题在引擎鉴权、长任务执行和线上排障场景下会显著降低可观测性。

## What Changes

- 新增 run 观测服务与 UI 页面：
  - `/ui/runs` 列表页（request_id 主键，关联 run_id）
  - `/ui/runs/{request_id}` 详情页（文件状态、文件树、只读预览）
  - `/ui/runs/{request_id}/logs/tail` 实时日志 tail
- 改造 adapter 进程输出采集为流式写盘：
  - 子进程运行期间持续写入 `logs/stdout.txt` 与 `logs/stderr.txt`
  - 保留现有 fail-fast 分类语义（`AUTH_REQUIRED` / `TIMEOUT`）
- 调整硬超时策略：
  - 默认值从 600s 提升到 1200s
  - 保持 `SKILL_RUNNER_ENGINE_HARD_TIMEOUT_SECONDS` 环境变量覆盖

## Impact

- 受影响代码：
  - `server/adapters/base.py`
  - `server/services/run_store.py`
  - `server/services/run_observability.py`
  - `server/routers/ui.py`
  - `server/assets/templates/ui/*`
  - `server/core_config.py`
- 受影响测试：
  - `tests/unit/test_adapter_failfast.py`
  - `tests/unit/test_run_observability.py`
  - `tests/unit/test_ui_routes.py`
  - `tests/unit/test_config.py`
- 文档：
  - `docs/api_reference.md`
