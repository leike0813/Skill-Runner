## Why

`interactive-00` 已引入 `execution_mode=auto|interactive`，但当前后端缺少“Skill 侧能力声明”校验。  
如果不增加声明与准入判断，前端可以对任意 Skill 发起 interactive 请求，导致不支持交互的 Skill 被错误执行。

## What Changes

1. 在 Skill `assets/runner.json` 中增加执行模式声明字段：
   - `execution_modes: ["auto" | "interactive", ...]`
   - 至少包含一个模式，且值必须在受支持枚举中。
2. 在 Job 创建阶段增加模式准入校验：
   - 若请求模式在 Skill 声明中，允许提交执行；
   - 若不在声明中，拒绝提交（400）。
3. 在 Skill 包校验链路增加声明校验：
   - 持久安装（`skill-package-install`）要求声明合法；
   - 临时上传执行（`ephemeral-skill-validation`）要求声明合法。
4. 定义兼容策略：
   - 对历史已安装且缺失 `execution_modes` 的 Skill，运行时按 `["auto"]` 兼容并输出 deprecation 告警；
   - 新上传/更新的 Skill 一律要求显式声明，避免继续产生无声明包。
5. 文档与测试同步：
   - API 文档说明模式准入错误语义；
   - Skill 包规范文档补充 `execution_modes` 字段。

## Capabilities

### New Capabilities
- `skill-execution-mode-declaration`: 定义 runner.json 的 `execution_modes` 声明语义及兼容策略。

### Modified Capabilities
- `interactive-job-api`: 在 run 创建阶段增加“请求模式是否被 skill 允许”的准入校验。
- `skill-package-install`: 新增安装时 `execution_modes` 合法性校验。
- `ephemeral-skill-validation`: 新增临时 skill 上传时 `execution_modes` 合法性校验。

## Impact

- `server/models.py`
- `server/services/skill_registry.py`
- `server/services/skill_package_validator.py`
- `server/routers/jobs.py`
- `server/routers/temp_skill_runs.py`
- `docs/api_reference.md`
- `docs/dev_guide.md`
- `tests/unit/test_v1_routes.py`
- `tests/unit/test_skill_package_validator.py`
- `tests/integration/test_temp_skill_runs_api.py`
