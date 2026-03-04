## Overview

本 change 在现有执行链路中新增一个独立的 `auth_detection` 层，用于在后台非交互任务执行结束后、generic `waiting_user` 推断前识别鉴权失败。实现采用混合模型：引擎专用 Python detector 负责结构化提取与上下文归一化，YAML rule pack 负责文本/字段匹配、分类映射与置信度配置。这样既能处理 `opencode` 多 provider 的复杂结构化错误，也能在未来通过低成本规则更新适应各 engine 的快速演进。

## Goals

- 将零散的全局 `AUTH_REQUIRED` regex 升级为可扩展、可审计、可测试的独立 detection 层。
- 在高置信度鉴权命中时，优先于 generic `waiting_user` 推断并强制使用 `failure_reason=AUTH_REQUIRED`。
- 在中低置信度命中时保持保守，不改变当前终态/等待态行为，但必须记录内部审计结果。
- 以 fixture 样本为第一版规则 SSOT，并允许未来通过 YAML 规则增量扩展。

## Non-Goals

- 不实现完整客户端鉴权流程、前端状态机或恢复执行协议。
- 不修改对外 HTTP API、FCMP 事件 schema 或 runtime contract schema。
- 不做规则热重载；第一波只支持启动时加载和校验。

## Architecture

### AuthDetectionService

新增 `server/runtime/auth_detection/service.py` 作为 detection 入口，负责：

- 收集 adapter 执行结果、runtime parse 结果与 parser diagnostics
- 调用 engine-specific detector 提取结构化证据
- 加载并评估 YAML rule packs
- 产出统一的 `AuthDetectionResult`

统一结果固定为：

- `classification`
- `subcategory`
- `confidence`
- `engine`
- `provider_id`
- `matched_rule_ids`
- `evidence_sources`
- `evidence_excerpt`
- `details`

### Hybrid Rule Architecture

#### Python detector 负责

- 引擎专用结构化提取
- 引擎专用上下文归一化
- 问题样本信号抽取
- 生成统一的 `AuthDetectionEvidence`

#### YAML rule pack 负责

- 文本/字段匹配表达式
- provider 维度分类映射
- 置信度配置
- 规则优先级
- 可启停规则项

规则目录固定为：

- `server/assets/auth_detection/common.yaml`
- `server/assets/auth_detection/codex.yaml`
- `server/assets/auth_detection/gemini.yaml`
- `server/assets/auth_detection/iflow.yaml`
- `server/assets/auth_detection/opencode.yaml`

对应 schema：

- `server/assets/schemas/auth_detection/rule_pack.schema.json`

仅允许以下 operator：

- `eq`
- `in`
- `regex`
- `contains`
- `gte`

任何 duplicate rule id、非法 operator、非法 subcategory 都在服务启动时 fail-fast。

### Detector Layout

新增 detector 文件：

- `server/engines/codex/auth/detection.py`
- `server/engines/gemini/auth/detection.py`
- `server/engines/iflow/auth/detection.py`
- `server/engines/opencode/auth/detection.py`

职责边界：

- `codex/gemini/iflow`：主要提取 combined text，依赖 YAML 文本强规则。
- `opencode`：必须从 stdout / structured rows 中提取 `error_name`、`status_code`、`message`、`provider_id`、`response_error_type`，并额外提取 `step_finish_unknown_count`、`saw_manual_interrupt` 供问题样本层使用。

### Rule Layering

第一版固定采用以下分层：

1. `Layer 0`：交互/TUI 背景参考层（`visit URL` / `authorization code`），不进入后台主规则库。
2. `Layer 1`：`opencode` 结构化强规则层。
3. `Layer 2`：`codex/gemini/iflow` 后台文本强规则层。
4. `Layer 3`：问题样本层，目前仅 `opencode/iflowcn_unknown_step_finish_loop`，只能产出 `medium`。
5. `Layer 4`：保守兜底层，输出 `not_auth` 或 `unknown`。

### Lifecycle Integration

主集成点位于 `server/services/orchestration/run_job_lifecycle_service.py`，顺序固定为：

1. adapter 执行完成
2. 收集 `ProcessExecutionResult`、`EngineRunResult`、runtime parse 结果
3. 调用 `AuthDetectionService.detect(...)`
4. `confidence=high` 时：
   - 强制 `failure_reason=AUTH_REQUIRED`
   - 跳过 generic pending interaction / `waiting_user` 推断
5. `confidence=medium|low` 时：
   - 不改变强制失败分类
   - 继续当前逻辑
   - 但必须写审计

### Audit Persistence

`RunAuditService.write_attempt_audit_artifacts()` 将新增 `auth_detection` 字段并写入 `.audit/meta.{attempt}.json`。同时在 parser diagnostics 输出中新增一条 `AUTH_DETECTION_MATCHED` 诊断记录，用于后续排查和规则调优。

`RunObservabilityService` 只需要能从 attempt meta 中读取 `auth_detection`，不新增对外 FCMP / SSE 字段。

### Legacy Fallback

`base_execution_adapter._looks_like_auth_required()` 保留，但降级为 legacy fallback：

- 仅在没有 `auth_detection` 结果时可生效
- 不再扩展新的主规则

## Risks and Mitigations

### 风险：高置信度 detection 误伤普通错误

对策：

- 第一版规则严格以 fixture 为 SSOT
- `Layer 0` 交互式 URL/code 提示不进入后台规则库
- 对问题样本层统一限制为 `medium`

### 风险：`opencode` 输出格式持续演进

对策：

- 结构化提取逻辑集中在 engine-specific detector
- 文本/字段匹配放到 YAML 中，降低后续升级成本

### 风险：在 lifecycle 中接入过晚，仍被 `waiting_user` 覆盖

对策：

- 将 detection 固定插在 pending interaction inference 之前
- 为高置信度命中增加集成测试，明确不能进入 `waiting_user`

### 风险：规则资产非法导致运行时行为不一致

对策：

- 启动时预加载并 schema 校验 rule packs
- 非法规则包直接 fail-fast 阻止服务进入可运行状态

## Validation

- `pytest tests/unit/test_auth_detection_rule_loader.py tests/unit/test_auth_detection_codex.py tests/unit/test_auth_detection_gemini.py tests/unit/test_auth_detection_iflow.py tests/unit/test_auth_detection_opencode.py tests/unit/test_auth_detection_lifecycle_integration.py tests/unit/test_auth_detection_audit_persistence.py`
- 如触达 runtime/observability，再补跑 `tests/unit/test_runtime_event_protocol.py tests/unit/test_run_observability.py`
- `mypy --follow-imports=skip server/runtime/auth_detection/*.py server/engines/*/auth/detection.py server/services/orchestration/run_job_lifecycle_service.py server/services/orchestration/run_interaction_lifecycle_service.py server/services/orchestration/run_audit_service.py server/runtime/observability/run_observability.py`
