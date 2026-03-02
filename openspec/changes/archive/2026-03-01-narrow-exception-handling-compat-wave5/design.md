## Context

当前 broad catch allowlist 基线（`server/`）为：
- total: 97
- pass: 14
- loop_control: 3
- return: 20
- log: 44
- other: 16

wave4 后剩余热点集中在 platform/orchestration 辅助链路：
- `server/services/platform/schema_validator.py`: total 5（return 4, other 1）
- `server/services/orchestration/agent_cli_manager.py`: total 5（log 2, return 1, other 2）
- `server/services/orchestration/run_audit_service.py`: total 4（loop_control 1, return 1, other 2）

这些分支中包含可判定的 file/parse/decode 异常处理，具备“可收窄优先”改造空间；同时少数 adapter/cleanup 场景仍需保留兼容性 fallback。

## Goals / Non-Goals

**Goals:**
- 在上述三个热点模块优先收窄 deterministic broad catch，降低 `other` 与不透明 fallback 比例。
- 对需保留 broad catch 的边界场景补齐结构化诊断字段与明确 fallback 语义。
- 维持现有 API、runtime 协议与行为语义，完成 allowlist 基线递减。

**Non-Goals:**
- 不改 HTTP API 契约、状态码及响应结构。
- 不改 runtime schema/invariants。
- 不进行跨模块架构重构，仅做局部异常治理与门禁收敛。

## Decisions

### 1) Wave5 实施顺序
1. `server/services/platform/schema_validator.py`
2. `server/services/orchestration/agent_cli_manager.py`
3. `server/services/orchestration/run_audit_service.py`
4. `docs/contracts/exception_handling_allowlist.yaml` + 门禁回归

理由：先处理 deterministic 校验路径，再处理 orchestration bootstrap，最后处理 audit 读取兼容路径，可在最小行为风险下获得最大净降幅。

### 2) 收窄规则矩阵
- `schema_validator`：
  - schema 文件读取：`OSError`
  - JSON 解析：`json.JSONDecodeError`
  - schema 校验：保留 `jsonschema.ValidationError`，其余失败分支按 typed exception 分类
- `agent_cli_manager`：
  - bootstrap json/text 读取：`OSError` + `json.JSONDecodeError`
  - settings/path resolve：`OSError`（必要时补 `ValueError`）
- `run_audit_service`：
  - JSONL 行解析：`json.JSONDecodeError`
  - 文件读取遍历：`OSError`
  - 对第三方 adapter parse 边界可保留 broad catch，但必须结构化诊断并标注 non-blocking fallback

### 3) 兼容性护栏
- 不改变现有 fallback 的成功/失败判定结果，仅提升异常类型精度和可观测性。
- 保持 orchestrator event `seq/history` 兼容旧数据读取语义。
- 保持 runtime 合同相关 payload 与状态迁移行为不变。

### 4) 验证门禁
- 优先门禁：`tests/unit/test_no_unapproved_broad_exception.py`
- 模块回归：`tests/unit/test_schema_validator.py`、`tests/unit/test_agent_cli_manager.py`、`tests/unit/test_job_orchestrator.py`
- runtime 合同回归（触达 orchestrator/history 路径时）：执行 AGENTS.md 必跑清单，并按需追加 `test_fcmp_cursor_global_seq.py`

## Risks / Trade-offs

- [Risk] 过度收窄导致未知异常上浮改变原有降级行为。  
  → Mitigation: 对不确定边界保留受控 broad catch，仅收窄 deterministic 分支。

- [Risk] 日志补强引入噪声或格式不一致。  
  → Mitigation: 统一结构化字段（`component/action/error_type/fallback`）并复用现有日志风格。

- [Risk] allowlist 基线更新滞后导致门禁误报。  
  → Mitigation: 将 allowlist 更新与门禁测试设为同一波次末尾的独立任务。

## Migration Plan

1. 按 wave5 顺序逐文件完成收窄，单文件完成后立即运行对应单测。  
2. 完成全部目标文件后重算 broad-catch 基线并更新 allowlist。  
3. 运行 AST 门禁 + 关键回归测试；若触达 runtime 协议/状态路径，执行 runtime 必跑清单。  
4. 如出现语义回归，按文件粒度回滚，不影响已验证模块。  

## Open Questions

- _None._
