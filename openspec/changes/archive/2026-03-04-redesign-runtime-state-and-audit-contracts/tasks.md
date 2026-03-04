# Tasks

- [x] 新增 `run-state-contract`、`run-audit-contract`、`runtime-dispatch-lifecycle`、`session-runtime-lifecycle` delta specs
- [x] 更新 `docs/contracts/session_fcmp_invariants.yaml`，增加 `.state/*` 与 dispatch 生命周期不变量
- [x] 更新 `runtime_contract.schema.json`，定义 `run_state_envelope`、`run_dispatch_envelope`、terminal-only `result`
- [x] 重写 `docs/run_artifacts.md`，明确 state files / audit files / terminal result / legacy files
- [x] 更新 `docs/session_runtime_statechart_ssot.md`，加入 dispatch subchart 和 state ownership layer
- [x] 更新 `docs/session_event_flow_sequence_fcmp.md`，加入 create -> dispatch -> claim -> running 时序
- [x] 更新 `docs/runtime_stream_protocol.md`，明确 FCMP 为 history truth、`.state/state.json` 为 current truth
- [x] 引入 `run_state.py`、`run_dispatch.py`、`run_audit_contract.py` 模型
- [x] 扩展 `run_store`，持久化 `request_run_state` 与 `request_dispatch_state`
- [x] 实现 `run_state_service`
- [x] 实现 `run_audit_contract_service`
- [x] 改造 `jobs.py` / `temp_skill_runs.py`，create-run 后立即写 `.state/*`
- [x] 改造 `run_job_lifecycle_service.py`，worker claim 先推进 dispatch phase，再 materialize attempt audit
- [x] 改造 waiting/auth/interaction/recovery，统一写入 `.state/state.json.pending`
- [x] 改造 observability 和 read facade，切换为 `.state/*` 优先读取
- [x] 改造前端与管理台，只用 state/dispatch/result 三层模型
- [x] 补齐 schema、store、router、observability、UI 回归测试
