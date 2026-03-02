## Context

当前 broad catch allowlist 基线（`server/`）为：
- total: 84
- pass: 14
- loop_control: 2
- return: 14
- log: 42
- other: 12

wave6 目标热点：
- `server/runtime/observability/run_observability.py`: total 5
- `server/services/skill/skill_patcher.py`: total 5
- `server/engines/gemini/adapter/trust_folder_strategy.py`: total 5
- `server/engines/codex/adapter/trust_folder_strategy.py`: total 4

这些路径包含多处 deterministic 的文件/解析/路径处理分支，具备可收窄空间；同时部分兼容性读取路径可能需要保留受控 broad catch。

## Goals / Non-Goals

**Goals:**
- 在上述 4 个热点文件优先收窄 deterministic broad catch，继续压降 `total` 与 `other`。
- 对必须保留的 broad catch 统一补齐结构化诊断字段并明确 fallback 意图。
- 保持 runtime observability 历史读取、cursor 语义与 skill patch 输出行为兼容。
- 完成 allowlist 基线递减并通过门禁回归。

**Non-Goals:**
- 不改 HTTP API 契约。
- 不改 runtime schema/invariants。
- 不引入新外部依赖，不做跨模块重构。

## Decisions

### 1) Wave6 实施顺序
1. `server/runtime/observability/run_observability.py`
2. `server/services/skill/skill_patcher.py`
3. `server/engines/gemini/adapter/trust_folder_strategy.py`
4. `server/engines/codex/adapter/trust_folder_strategy.py`
5. allowlist 与门禁回归

理由：先处理 runtime 核心观测路径，再推进 skill/adapter 链路，可在兼容风险可控前提下获得最大净降幅。

### 2) 收窄规则
- 文件 IO：优先 `OSError` / `UnicodeDecodeError`
- JSON/文本解析：优先 `json.JSONDecodeError` / `ValueError`
- 路径归一化与解析：优先 `OSError` / `ValueError` / 相关路径异常
- 仅在无法静态枚举的边界输入场景保留 broad catch，并要求 structured log

### 3) 兼容性护栏
- 不改变 runtime 事件语义、seq/cursor/history 输出。
- 不改变 skill patch 对外返回结构与错误映射语义。
- trust-folder 行为语义保持不变，仅提升异常诊断精度。

### 4) 验证门禁
- Broad catch 门禁：`tests/unit/test_no_unapproved_broad_exception.py`
- 模块回归：
  - `tests/unit/test_run_observability.py`
  - `tests/unit/test_runtime_observability_port_injection.py`
  - `tests/unit/test_skill_patcher.py`
  - `tests/unit/test_skill_patcher_pipeline.py`
  - `tests/unit/test_codex_adapter.py`
  - `tests/unit/test_gemini_adapter.py`
- runtime 合同回归（触达 runtime observability 路径）：
  - `tests/unit/test_session_invariant_contract.py`
  - `tests/unit/test_session_state_model_properties.py`
  - `tests/unit/test_fcmp_mapping_properties.py`
  - `tests/unit/test_protocol_state_alignment.py`
  - `tests/unit/test_protocol_schema_registry.py`
  - `tests/unit/test_runtime_event_protocol.py`
  - `tests/unit/test_run_observability.py`
  - `tests/unit/test_fcmp_cursor_global_seq.py`

## Risks / Trade-offs

- [Risk] runtime observability 过度收窄导致历史兼容读取回归。  
  → Mitigation: 对旧数据不确定边界保留受控 broad catch，并补齐 structured log。

- [Risk] skill patch 收窄后暴露此前被吞没的异常。  
  → Mitigation: 仅收窄 deterministic 分支，保留已有 fallback 语义与返回格式。

- [Risk] allowlist 同步不及时触发门禁失败。  
  → Mitigation: 将 allowlist 更新和 AST 门禁作为同一波次末尾的强制步骤。

## Migration Plan

1. 按 wave6 顺序逐文件收窄并保持行为兼容。  
2. 每个目标文件完成后运行对应模块测试。  
3. 更新 allowlist 基线并执行 AST 门禁。  
4. 运行 runtime 合同回归，确认无协议/状态漂移。  

## Open Questions

- _None._
