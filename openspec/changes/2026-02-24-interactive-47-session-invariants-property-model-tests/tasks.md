## 1. OpenSpec & Contract

- [x] 1.1 新增 change：`interactive-47-session-invariants-property-model-tests`
- [x] 1.2 新增 `session-runtime-invariant-contract` capability
- [x] 1.3 修改 `session-runtime-statechart-ssot` / `interactive-log-sse-api` / `runtime-event-command-schema` 要求

## 2. Invariant SSOT

- [x] 2.1 新增 `docs/contracts/session_fcmp_invariants.yaml`
- [x] 2.2 定义 canonical 状态集合、终态集合、转移集合
- [x] 2.3 定义 FCMP state_changed 映射、paired events、ordering rules

## 3. Tests

- [x] 3.1 新增 `tests/common/session_invariant_contract.py`
- [x] 3.2 新增 `tests/unit/test_session_invariant_contract.py`
- [x] 3.3 新增 `tests/unit/test_session_state_model_properties.py`
- [x] 3.4 新增 `tests/unit/test_fcmp_mapping_properties.py`
- [x] 3.5 修改 `tests/unit/test_session_statechart_contract.py` 使用合同驱动
- [x] 3.6 修改 `tests/unit/test_protocol_state_alignment.py` 使用合同驱动

## 4. Docs

- [x] 4.1 `docs/session_runtime_statechart_ssot.md` 增加 Canonical Invariants 引用
- [x] 4.2 `docs/session_event_flow_sequence_fcmp.md` 标注 invariant 锚点

## 5. Validation

- [x] 5.1 运行 `test_session_invariant_contract.py`
- [x] 5.2 运行 `test_session_state_model_properties.py`
- [x] 5.3 运行 `test_fcmp_mapping_properties.py`
- [x] 5.4 回归运行 `test_session_statechart_contract.py` / `test_protocol_state_alignment.py`
- [x] 5.5 回归运行 `test_runtime_event_protocol.py` / `test_run_observability.py`
