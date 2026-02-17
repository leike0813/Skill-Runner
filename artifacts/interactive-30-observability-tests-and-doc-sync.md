# interactive-30-observability-tests-and-doc-sync 实现记录

## 实现范围
- 补齐 `GET /v1/jobs/{request_id}` 的交互可观测字段：
  - `pending_interaction_id`
  - `interaction_count`
- 保持并验证 `waiting_user` 下日志轮询建议：
  - `run_observability.get_logs_tail(...).poll == false`
  - `run_observability.get_run_detail(...).poll_logs == false`
- 扩展交互生命周期测试矩阵：
  - 单元：`waiting_user` 状态展示与 `poll=false`
  - 集成：reply 成功/冲突/非 waiting 分支、cancel 语义与 SSE 一致性
  - e2e runner：支持按 `interactive_replies` 自动走 `pending -> reply -> terminal`
- 文档同步：
  - API 参考补充 `RequestStatusResponse` 交互字段与 `waiting_user` 非终态说明
  - 开发指南明确 non-interactive 约束由 `runtime_options.execution_mode` 判定
  - 增加“外部优先 API、内建 UI 同步遵循统一契约”的边界说明

## 关键变更文件
- `server/models.py`
- `server/routers/jobs.py`
- `tests/unit/test_jobs_interaction_routes.py`
- `tests/unit/test_run_observability.py`
- `tests/integration/test_jobs_interactive_observability.py`
- `tests/e2e/run_e2e_tests.py`
- `docs/api_reference.md`
- `docs/dev_guide.md`

## 回归与验证
- 相关单测：
  - `conda run --no-capture-output -n DataProcessing python -m pytest tests/unit/test_jobs_interaction_routes.py tests/unit/test_run_observability.py -q`
  - 结果：`22 passed`
- 新增集成测试：
  - `conda run --no-capture-output -n DataProcessing python -m pytest tests/integration/test_jobs_interactive_observability.py -q`
  - 结果：`3 passed`
- 类型检查：
  - `conda run --no-capture-output -n DataProcessing python -m mypy server`
  - 结果：`Success: no issues found in 52 source files`
- 全量单元测试门禁：
  - `conda run --no-capture-output -n DataProcessing python -m pytest tests/unit -q`
  - 结果：`332 passed`

## OpenSpec 流程记录
- `openspec status --change "interactive-30-observability-tests-and-doc-sync" --json`
- `openspec validate "interactive-30-observability-tests-and-doc-sync" --type change --strict`
  - 结果：`valid`
- `openspec archive "interactive-30-observability-tests-and-doc-sync" -y`
  - 归档目录：`openspec/changes/archive/2026-02-16-interactive-30-observability-tests-and-doc-sync`
