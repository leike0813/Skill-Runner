# interactive-26-job-termination-api-and-frontend-control 实现记录

## 变更范围
- 取消 API：
  - 新增 `POST /v1/jobs/{request_id}/cancel`
  - 新增 `POST /v1/temp-skill-runs/{request_id}/cancel`
  - 返回统一 `CancelResponse`，覆盖活跃态取消与终态幂等语义
- 运行时取消链路：
  - `run_store` 增加 `cancel_requested` 持久字段与读写接口
  - `job_orchestrator` 新增取消短路、运行中取消、统一 `canceled` 收尾与错误码写入
  - adapter 基座支持按 run_id 跟踪活动进程并执行终止
- 可观测性对齐：
  - SSE `status` 事件携带取消错误码（`CANCELED_BY_USER`）
  - 状态查询与结果文件统一呈现 `RunStatus.CANCELED` 与错误对象
- 文档更新：
  - `docs/api_reference.md` 增加 cancel 接口与语义说明
  - `docs/dev_guide.md` 增加取消生命周期说明

## 测试与校验
- 全量单元测试：
  - `307 passed`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m pytest tests/unit -q`
- 类型检查：
  - `Success: no issues found in 51 source files`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m mypy server`
- OpenSpec：
  - `openspec validate interactive-26-job-termination-api-and-frontend-control --type change --strict --no-interactive`
  - `openspec archive interactive-26-job-termination-api-and-frontend-control -y`
  - 归档目录：`openspec/changes/archive/2026-02-16-interactive-26-job-termination-api-and-frontend-control`
  - 同步 spec：
    - `openspec/specs/interactive-job-cancel-api/spec.md`
    - `openspec/specs/interactive-run-cancel-lifecycle/spec.md`
    - `openspec/specs/interactive-log-sse-api/spec.md`（更新）
