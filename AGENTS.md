# AGENTS.md — Runtime Core SSOT Navigation

## 最小背景
Skill Runner 是一个多引擎（`codex` / `gemini` / `iflow`）的 skill 执行编排服务。  
当前项目的核心目标是：在统一状态机下稳定执行会话、输出结构化结果、并提供可审计的事件流。  
运行时协议已收敛为 FCMP 对外单流 + RASP 审计内核。  
`interactive` 与 `auto` 共享同一 canonical statechart，`auto` 是 `interactive` 的受限子集。  
本文件不是需求文档，而是 **SSOT 导航与防漂移约束**。

## SSOT 优先级（冲突判定）
当定义冲突时，按以下优先级裁决（高 -> 低）：
1. 机器可读合同（JSON Schema / invariants YAML）
2. OpenSpec 主规格（`openspec/specs/*`）
3. 叙述文档（`docs/*`）
4. 代码实现（`server/*`）
5. 历史 change 文档（`openspec/changes/*`）

## Runtime 核心 SSOT 映射
| SSOT 元 | Definition（定义文件） | Docs（文档文件） | Implementation（实现文件） |
|---|---|---|---|
| Session Canonical Statechart | `docs/contracts/session_fcmp_invariants.yaml`（`canonical` / `transitions`） | `docs/session_runtime_statechart_ssot.md` | `server/services/session_statechart.py`、`server/services/job_orchestrator.py` |
| FCMP 单流事件语义与时序 | `docs/contracts/session_fcmp_invariants.yaml`（`fcmp_mapping` / `ordering_rules`） | `docs/session_event_flow_sequence_fcmp.md`、`docs/runtime_stream_protocol.md` | `server/services/runtime_event_protocol.py`、`server/services/run_observability.py`、`server/services/protocol_factories.py`、`server/models.py` |
| 运行时事件/命令 Schema 合同 | `server/assets/schemas/protocol/runtime_contract.schema.json` | `docs/runtime_event_schema_contract.md` | `server/services/protocol_schema_registry.py`、`server/services/runtime_event_protocol.py`、`server/services/run_store.py`、`server/services/run_observability.py` |
| 不变量守护与模型验证 | `docs/contracts/session_fcmp_invariants.yaml` | `docs/session_runtime_statechart_ssot.md`（Canonical Invariants） | `tests/common/session_invariant_contract.py`、`tests/unit/test_session_invariant_contract.py`、`tests/unit/test_session_state_model_properties.py`、`tests/unit/test_fcmp_mapping_properties.py`、`tests/unit/test_protocol_state_alignment.py` |

## Runtime 变更硬门禁（必须同时满足）
任何 runtime 行为改动必须按以下顺序推进：
1. 先改定义文件（`runtime_contract.schema.json` 或 `session_fcmp_invariants.yaml`）
2. 再改文档（statechart / sequence / OpenSpec specs）
3. 再改实现（factory / protocol / orchestrator / observability）
4. 最后改测试（合同测试、属性/模型测试、回归测试）

### 禁止项
- 禁止在业务层直接手拼核心 FCMP/RASP payload（必须走 `server/services/protocol_factories.py`）。
- 禁止只改代码不改 SSOT（schema/invariants/spec 至少同步一处）。
- 禁止新增事件类型却不更新 `server/models.py` + schema + tests。

## 必跑测试清单（runtime 相关改动）
```bash
conda run --no-capture-output -n DataProcessing python -u -m pytest \
  tests/unit/test_session_invariant_contract.py \
  tests/unit/test_session_state_model_properties.py \
  tests/unit/test_fcmp_mapping_properties.py \
  tests/unit/test_protocol_state_alignment.py \
  tests/unit/test_protocol_schema_registry.py \
  tests/unit/test_runtime_event_protocol.py \
  tests/unit/test_run_observability.py
```

若改动涉及 `seq/cursor/history`，追加：
```bash
conda run --no-capture-output -n DataProcessing python -u -m pytest \
  tests/unit/test_fcmp_cursor_global_seq.py
```

若改动涉及问询/回复去重语义，追加：
```bash
conda run --no-capture-output -n DataProcessing python -u -m pytest \
  tests/unit/test_fcmp_interaction_dedup.py
```

## SSOT 漂移 PR 自检清单
1. 是否出现了新的 state/event 名称但未更新 `docs/contracts/session_fcmp_invariants.yaml`？
2. 是否修改了 `interaction.reply.accepted` 语义但未更新 sequence 文档与 paired 规则？
3. 是否修改了 `conversation.state.changed` 的 `from/to/trigger` 语义却未更新 invariants 映射？
4. 是否修改了 `seq` 语义却未同步 `events/history`、SSE cursor 以及对应测试？
5. 是否新增/修改 FCMP 或 RASP payload 字段但未更新 `runtime_contract.schema.json`？
6. 是否绕过了 `protocol_factories` 在业务代码中直接拼装核心事件？
7. 是否调整了状态迁移逻辑却未同步 `session_statechart.py` 与模型测试？
8. 是否变更了 observability/history 读取策略却未覆盖旧数据兼容场景？
9. 是否改动了 waiting/reply/auto-decide 行为却未跑 FCMP 配对与顺序测试？
10. 是否存在“测试通过但文档未同步”的情况？

## Public API / Types 影响说明
本文件是治理入口文档，本次重写不直接改变：
- 对外 HTTP API
- 运行时协议类型
- 数据模型定义

## 范围声明
- 文件名以 `AGENTS.md` 为准，不新增 `Agent.md`。
- 本文件聚焦 runtime 核心 SSOT，不扩展到 skill patch、UI 视觉细节、部署流程。
