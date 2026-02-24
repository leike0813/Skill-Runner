## Why

`interactive-45/46` 已完成 FCMP 单流与 Schema 合同化，但当前“文档约束 -> 测试守护”仍不够直接：

- 关键不变量散落在文档和单测中；
- 核心断言仍存在硬编码，容易与文档漂移；
- 缺少针对状态机/事件映射的模型化属性测试。

需要新增独立 change，把不变量收敛为机器可读合同，并让测试直接消费该合同。

## Dependencies

- 依赖 `interactive-45-fcmp-single-stream-event-architecture`（FCMP 单流事件面）。
- 依赖 `interactive-46-event-command-schema-contract`（Schema 合同化与运行时校验）。

## What Changes

1. 新增不变量合同文件：`docs/contracts/session_fcmp_invariants.yaml`。
2. 新增测试公共加载器：`tests/common/session_invariant_contract.py`。
3. 新增合同/模型/属性测试：
   - `test_session_invariant_contract.py`
   - `test_session_state_model_properties.py`
   - `test_fcmp_mapping_properties.py`
4. 收敛既有测试，移除状态/触发器硬编码：
   - `test_session_statechart_contract.py`
   - `test_protocol_state_alignment.py`
5. 文档补充 invariant 锚点：
   - `docs/session_runtime_statechart_ssot.md`
   - `docs/session_event_flow_sequence_fcmp.md`

## Capabilities

### Modified
- `session-runtime-statechart-ssot`
- `interactive-log-sse-api`
- `runtime-event-command-schema`

### Added
- `session-runtime-invariant-contract`

## Impact

- 不改对外 API 路径与事件名；
- 不新增运行时分支语义；
- 提升“文档 -> 测试 -> 实现”一致性与回归防漂移能力。

## Follow-up

- `interactive-48-skill-patch-modular-injection`：统一 skill patch 注入流程并消除 server/harness 注入分叉。
