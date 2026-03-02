## 1. OpenSpec Artifacts

- [x] 1.1 创建 `proposal.md`，定义治理目标、范围和兼容约束
- [x] 1.2 创建 `specs/exception-handling-hardening/spec.md`，定义门禁与分层治理要求
- [x] 1.3 创建 `design.md`，明确白名单基线 + AST 门禁设计

## 2. Baseline and Guardrail

- [x] 2.1 新增 `docs/contracts/exception_handling_allowlist.yaml`，固化当前 broad catch 基线统计
- [x] 2.2 新增 `tests/unit/test_no_unapproved_broad_exception.py`，实现 AST 扫描门禁
- [x] 2.3 在门禁测试中校验“新增文件/计数超基线”必失败

## 3. Core Narrowing (Compatibility-first)

- [x] 3.1 收窄 `server/services/orchestration/job_orchestrator.py` 中可安全场景的 broad catch
- [x] 3.2 收窄 `server/services/orchestration/run_interaction_lifecycle_service.py` 中可安全场景的 broad catch
- [x] 3.3 为保留 broad catch 的路径补充策略语义注释/上下文说明

## 4. Validation

- [x] 4.1 运行异常门禁测试并确认通过
- [x] 4.2 运行核心回归测试：
  - `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_job_orchestrator.py tests/unit/test_runtime_event_protocol.py tests/unit/test_run_observability.py`
- [x] 4.3 运行 runtime 合同相关回归：
  - `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_session_invariant_contract.py tests/unit/test_session_state_model_properties.py tests/unit/test_fcmp_mapping_properties.py tests/unit/test_protocol_state_alignment.py tests/unit/test_protocol_schema_registry.py`

## 5. Router Wave (In Progress)

- [x] 5.1 收窄 `server/routers/jobs.py` 的可判定 broad catch（解析路径）
- [x] 5.2 收窄 `server/routers/management.py` 的可判定 broad catch（解析/I-O 路径）
- [x] 5.3 收窄 `server/routers/temp_skill_runs.py` 的可判定 broad catch（解析路径）
- [x] 5.4 为保留的 router 边界层 broad catch 增加结构化日志字段与降级说明

## 6. Router Wave (Engines Boundary Hardening)

- [x] 6.1 在 `server/routers/engines.py` 引入统一内部错误映射 helper，收敛重复 broad catch 处理分支
- [x] 6.2 为 `server/routers/engines.py` 的 broad catch 路径补充结构化日志（component/action/error_type/fallback）
- [x] 6.3 保持 `HTTP 500 + detail=str(exc)` 与 callback 500 错误页语义不变

## 7. Router Wave (UI Boundary Hardening)

- [x] 7.1 在 `server/routers/ui.py` 引入统一内部错误映射 helper，收敛重复 broad catch 处理分支
- [x] 7.2 为 `server/routers/ui.py` 的 broad catch 路径补充结构化日志（component/action/error_type/fallback）
- [x] 7.3 保持 UI 鉴权会话相关接口的 `HTTP 500 + detail=str(exc)` 兼容语义

## 8. Runtime Adapter Wave (base_execution_adapter)

- [x] 8.1 收窄 `server/runtime/adapter/base_execution_adapter.py` 中的 broad catch（进程终止、JSON 解析、类型转换）
- [x] 8.2 清理 `pass` 式吞没分支，改为“具体异常 + 降级路径日志”
- [x] 8.3 保持超时终止、回退 kill、交互 payload 解析的兼容语义
- [x] 8.4 同步 `exception_handling_allowlist` 基线计数，锁定本轮收敛成果

## 9. Runtime Auth Wave (session_lifecycle)

- [x] 9.1 为 `server/runtime/auth/session_lifecycle.py` 中保留的 broad catch 增加 best-effort cleanup 注释与边界语义说明
- [x] 9.2 明确“cleanup 失败不得遮蔽主异常 + 必须释放交互锁”的兼容行为约束
