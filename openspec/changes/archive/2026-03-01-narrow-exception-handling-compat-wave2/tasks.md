## 1. Baseline and Scope Freeze

- [x] 1.1 记录本 change 起点基线（`server/` broad catch total=209）并在 PR 描述中固定统计口径
- [x] 1.2 识别本轮优先清理目标：`pass/return` 吞没点 + 热点文件 `other` 分类
- [x] 1.3 为每个目标文件标记“可收窄”与“需保留 broad catch”位置

## 2. Wave A — Engine Auth Common

- [x] 2.1 收窄 `server/engines/common/openai_auth/common.py` 中可确定异常域的 broad catch
- [x] 2.2 对保留 broad catch 分支补充策略注释（boundary/best-effort）与结构化日志上下文
- [x] 2.3 跑该模块相关回归并确认失败语义兼容

## 3. Wave B — Run Store

- [x] 3.1 收窄 `server/services/orchestration/run_store.py` 中 parse/convert/I-O 场景 broad catch
- [x] 3.2 清理 `pass` 与 silent-return 类型吞没，保留必要 fallback
- [x] 3.3 运行 `run_store` 与相关 orchestrator 回归测试

## 4. Wave C — Engine Auth Protocol Paths

- [x] 4.1 收窄 `server/engines/gemini/auth/protocol/oauth_proxy_flow.py` 高风险 broad catch
- [x] 4.2 收窄 `server/engines/iflow/auth/protocol/oauth_proxy_flow.py` 高风险 broad catch
- [x] 4.3 收窄 `server/engines/opencode/auth/protocol/google_antigravity_oauth_proxy_flow.py` 高风险 broad catch
- [x] 4.4 保留 broad catch 的分支补充可诊断上下文与降级注释

## 5. Wave D — Runtime/Auth Residual

- [x] 5.1 继续收敛 `server/runtime/auth/*` 剩余可判定 broad catch
- [x] 5.2 审查 `server/routers/engines.py`、`server/routers/ui.py` 中仍为 `other` 的边界映射分支并补齐策略语义
- [x] 5.3 完成 residual 文件的兼容性回归

## 6. Guardrail and Baseline Ratchet

- [x] 6.1 更新 `docs/contracts/exception_handling_allowlist.yaml` 到本轮新低基线
- [x] 6.2 验证 `tests/unit/test_no_unapproved_broad_exception.py` 全程通过
- [x] 6.3 输出“波次前后”统计对比（total/pass/return/log/other）

## 7. Validation Gate

- [x] 7.1 `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_no_unapproved_broad_exception.py`
- [x] 7.2 `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_engine_auth_flow_manager.py tests/unit/test_adapter_parsing.py tests/unit/test_adapter_failfast.py`
- [x] 7.3 `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_session_invariant_contract.py tests/unit/test_session_state_model_properties.py tests/unit/test_fcmp_mapping_properties.py tests/unit/test_protocol_state_alignment.py tests/unit/test_protocol_schema_registry.py tests/unit/test_runtime_event_protocol.py tests/unit/test_run_observability.py`
