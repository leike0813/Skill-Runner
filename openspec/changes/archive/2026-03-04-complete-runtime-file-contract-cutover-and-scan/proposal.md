# Proposal: Complete Runtime File Contract Cutover And Scan

## Why

当前 runtime 已经完成了 `.state/.audit/result` 主合同的大部分重构，但仓库中仍存在明显残留：

- 生产代码仍会创建或提及 legacy 目录/文件，例如 `interactions/`、`status.json`
- 测试夹具仍大量生成或读取 legacy 文件
- 主文档和主 spec 仍存在旧文件协议描述
- reset 流程没有完全与“全量强切换”后的目录骨架对齐

这些残留会导致三个实际问题：

1. 新 run 目录结构不稳定，容易再次漂移
2. observability / UI / API 仍可能从错误来源读取当前态
3. reset 之后不能保证系统只运行在新协议上

## What Changes

本 change 完成一次“文件协议最终切换”，并明确：

1. 新 run 只允许以下 canonical 文件协议：
   - `.state/state.json`
   - `.state/dispatch.json`
   - `.audit/request_input.json`
   - `.audit/meta.<attempt>.json`
   - `.audit/*.jsonl|*.log|*.json`
   - `result/result.json`
   - run-local skill snapshot
2. 新 run 完全禁止生成 legacy 文件或 legacy 目录：
   - `status.json`
   - `current/projection.json`
   - `interactions/`
   - `logs/`
   - `raw/`
   - 根目录 `input.json`
3. 所有新 run 的读取路径不再对 legacy 文件 fallback
4. `DataResetService` 和 `reset_project_data.py` 与新文件合同完全对齐
5. 新增自动扫描/守卫测试，阻止未来重新引入 legacy 文件协议
6. temp skill 在 create-run 时直接解包到 run-local skill snapshot，后续 attempt/resume 不再依赖 staging 目录或上传 zip

## Impact

- 新增 OpenSpec specs：
  - `run-file-contract`
  - `runtime-dispatch-state`
  - `runtime-audit-contract`
  - `runtime-data-reset`
- 更新 SSOT：
  - `docs/run_artifacts.md`
  - `docs/runtime_stream_protocol.md`
  - `docs/runtime_event_schema_contract.md`
  - `docs/session_runtime_statechart_ssot.md`
  - `docs/session_event_flow_sequence_fcmp.md`
  - `docs/dev_guide.md`
  - `docs/test_framework_design.md`
  - `docs/contracts/session_fcmp_invariants.yaml`
  - `server/assets/schemas/protocol/runtime_contract.schema.json`
  - `openspec/specs/job-orchestrator-modularization/spec.md`
- 更新实现：
  - create-run / state / audit / observability / reset / routers / UI 全部切到新文件协议
  - temp skill 与普通 skill 一样在 run 创建时直接 materialize 到 run-local snapshot
- 更新测试：
  - API integration、observability、UI、bundle、engine/harness fixture 统一迁移到 `.state/.audit/result`
