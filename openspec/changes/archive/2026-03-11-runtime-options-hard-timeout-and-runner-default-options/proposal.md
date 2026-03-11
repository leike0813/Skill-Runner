## Why

当前运行参数体系存在两个缺口：

1. `hard_timeout_seconds` 已在执行链路实现并生效，但未在 `runtime_options` 白名单中正式开放，导致 API 用户无法按契约使用该能力。
2. Skill 层缺少“默认 runtime options”声明能力。`runner.json` 目前只能声明执行模式与 schema/config 资产，无法为同一 skill 提供稳定默认运行参数，导致调用方重复传参。

同时，本次需要保持风险可控：
- 不引入新的运行语义分支；
- 不改 UI 预填；
- 无效默认值不阻断执行，但必须可观测。

## What Changes

- 正式开放 `runtime_options.hard_timeout_seconds`：
  - 加入 runtime option allowlist；
  - 增加正整数校验；
  - 文档明确默认值来源与覆盖优先级。
- 在 `runner.json` 增加 `runtime.default_options`：
  - 作为 skill 默认 runtime options；
  - 仅允许白名单键参与合成；
  - 请求体传值覆盖 skill 默认值。
- 无效默认值处理统一为“忽略并告警”：
  - 服务日志记录；
  - run 生命周期 warnings/diagnostic 可见（不阻断）。
- 统一 create/upload 两条链路的默认值合成行为（已安装 skill 与 temp_upload 一致）。

## Capabilities

### Modified Capabilities

- `engine-hard-timeout-policy`: `hard_timeout_seconds` 从“内部可用”升级为“API 合同可用”。
- `interactive-job-api`: `/v1/jobs` runtime option 合成语义扩展为“skill 默认 + 请求覆盖”。
- `skill-package-validation-schema`: `runner.json` 合同支持 `runtime.default_options` 声明。

## Impact

- Affected code:
  - `server/config/policy/options_policy.json`
  - `server/services/platform/options_policy.py`
  - `server/services/orchestration/run_execution_core.py`
  - `server/routers/jobs.py`
  - `server/services/orchestration/run_job_lifecycle_service.py`
  - `server/services/orchestration/run_store.py`
  - `server/models/skill.py`
  - `server/contracts/schemas/skill/skill_runner_manifest.schema.json`
- API impact:
  - `POST /v1/jobs` 可接收 `runtime_options.hard_timeout_seconds`。
  - `runner.json` 合同增量支持 `runtime.default_options`。
  - 不新增/删除 HTTP 路由。
