## Design Overview

本 change 保持现有规则模型（`id/enabled/priority/match/classify`）不变，只调整“来源”和“触发时机”。

## 1. Rule Source Hard Cut

- Adapter profile schema 新增 `auth_detection.rules`。
- 每个引擎 profile 内嵌该引擎全部鉴权规则。
- `AuthDetectionRuleRegistry` 通过 `load_adapter_profile` 读取规则并按 `priority` 排序。
- 运行时不再读取 `server/engines/auth_detection/*.yaml`。

## 2. Incremental Detection + Early Exit

`EngineExecutionAdapter._capture_process_output` 在读流期间执行增量检测：

1. 按节流频率用当前 stdout/stderr 调用 `parse_runtime_stream`（best-effort）构造 `runtime_parse_result`。
2. 调用同一 `auth_detection_service.detect(...)`。
3. 当检测到 `auth_required + high` 后进入“armed”状态。
4. 若后续输出空闲时间超过 `AUTH_DETECTION_IDLE_GRACE_SECONDS` 且进程仍存活，触发提前终止并标记 `failure_reason=AUTH_REQUIRED`。

说明：
- 该机制对所有引擎统一启用，但只有规则命中才会触发。
- CLI Delegate 鉴权链路不改，仍由 `engine_auth_flow_manager` 驱动。

## 3. Gemini New Prompt Style

- Gemini parser 新增诊断码：`GEMINI_OAUTH_CODE_PROMPT_DETECTED`。
- 诊断触发条件为 URL 授权提示 + 授权码输入提示的组合。
- 规则只匹配诊断码，不直接匹配交互文案。

## 4. Config

- 新增全局配置键：`SYSTEM.AUTH_DETECTION_IDLE_GRACE_SECONDS`（默认 `3`）。
- 不引入 per-engine 阈值，保持模型简单。
