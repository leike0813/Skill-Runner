# interactive-00 实现记录

## 变更目标
- 引入 `runtime_options.execution_mode`（默认 `auto`）
- 新增 Jobs 交互接口：
  - `GET /v1/jobs/{request_id}/interaction/pending`
  - `POST /v1/jobs/{request_id}/interaction/reply`
- 明确 400/404/409 语义
- `interactive` 模式跳过缓存命中且不写入缓存

## 主要实现
- 模型扩展：
  - `RunStatus` 新增 `waiting_user`
  - 新增 `ExecutionMode`
  - 新增交互相关模型：`PendingInteraction`、`InteractionReplyRequest`、`InteractionPendingResponse`、`InteractionReplyResponse`
- 运行时选项策略：
  - `options_policy` 新增 `execution_mode` allowlist
  - 自动注入默认值 `execution_mode=auto`
  - 校验仅允许 `auto|interactive`
- 路由实现：
  - 新增 pending/reply 两个 API
  - reply 支持 `idempotency_key` 幂等重放
  - 非 interactive 模式请求交互端点返回 400
  - stale interaction / idempotency 冲突返回 409
- 缓存策略：
  - `create_run` 与 `upload_file` 路径在 interactive 模式下跳过缓存命中
  - interactive 模式下向 orchestrator 传递 `cache_key=None`，避免写入 `cache_entries`
- 存储扩展：
  - `run_store` 新增 `request_interactions` 表
  - 新增 pending 读写与 reply 提交方法

## 测试与类型检查
- 全量单元测试：
  - `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit -q`
  - 结果：`241 passed`
- 类型检查：
  - `conda run --no-capture-output -n DataProcessing python -u -m mypy server`
  - 结果：`Success: no issues found in 50 source files`

## OpenSpec 验证与归档
- 验证：
  - `openspec validate "interactive-00-api-mode-and-interaction-contract" --type change --strict --no-interactive`
  - 结果：`valid`
- 归档：
  - `openspec archive "interactive-00-api-mode-and-interaction-contract" -y`
  - 归档目录：`openspec/changes/archive/2026-02-16-interactive-00-api-mode-and-interaction-contract`
  - 同步结果：`openspec/specs/interactive-job-api/spec.md` 已更新
