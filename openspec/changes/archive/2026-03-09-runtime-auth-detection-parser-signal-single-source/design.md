## Design Overview

本 change 采用“声明单源 + parser 直接信号”的简化模型：

1. 规则声明只在 adapter profile。
2. parser 直接产 `auth_signal`。
3. 运行时与生命周期只消费 `auth_signal`。
4. rule-registry 不再参与运行判定主链路。

## 1. Single Source Declaration

- `adapter_profile_schema.json` 将 `auth_detection.rules` 收敛为 `parser_auth_patterns.rules`。
- 规则结构保持不变（`id/enabled/priority/match/classify`），避免迁移时重写语义。
- 四个引擎 profile 全量迁移到 `parser_auth_patterns.rules`。

## 2. Parser Emits AuthSignal

- `RuntimeStreamParseResult` 扩展可选字段 `auth_signal`。
- 新增共享匹配器 `parser_auth_signal_matcher`，parser 通过它对声明规则做匹配并产出：
  - `required`
  - `confidence`
  - `subcategory`
  - `provider_id`
  - `reason_code`
  - `matched_pattern_id`
- diagnostics 保留用于可观测，不再承担主判定语义。

## 3. Runtime Early Exit

- `base_execution_adapter` 增量探测从 `runtime_parse_result.auth_signal` 读取信号。
- 当命中 `required + high` 并满足 idle 阈值时 early-exit，`failure_reason=AUTH_REQUIRED`。
- 移除基于 `combined_text` 的 fallback regex 判定，避免双语义并存。

## 4. Lifecycle Classification

- `run_job_lifecycle_service` 在终态归一化阶段使用 `auth_signal` 生成 `AuthDetectionResult`，用于：
  - waiting_auth 进入判定
  - 审计与诊断落盘
- 不再调用 rule-based detection 进行二次分类。

## 5. Compatibility Boundaries

- CLI Delegate 鉴权链路不改（仅 run adapter 执行路径受影响）。
- 外部 API 与事件类型不变，属于内部执行与可观测一致性改造。
