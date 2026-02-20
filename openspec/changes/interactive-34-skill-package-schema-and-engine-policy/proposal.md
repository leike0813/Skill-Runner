## Why

当前 skill 包校验规则主要固化在服务代码中，缺少独立的校验合同文件，导致规则演进成本高、跨入口一致性难以保证。  
同时 `runner.json.engines` 目前是强制字段，无法表达“默认支持全部引擎 + 局部禁用”的策略，也不利于前端读取统一可选项。

## What Changes

- 新增独立的 skill package 校验 schema（含 `runner.json` 合同），并在安装与临时上传校验中统一复用。
- 新增 `input.schema.json`、`parameter.schema.json`、`output.schema.json` 的 meta-schema，并在上传校验阶段做结构预检。
- 将 `runner.json.engines` 从“必填非空”调整为“可选”。
- 新增 `runner.json.unsupported_engines` 字段用于声明不支持的引擎。
- 当 `engines` 与 `unsupported_engines` 同时存在时，系统必须校验两者无重复项。
- 定义并落实“有效引擎集合”语义：`effective_engines = (engines 或 系统全量支持引擎) - unsupported_engines`。
- 运行请求若命中不支持引擎（含落在 `unsupported_engines` 或不在 `effective_engines`）必须拒绝执行并返回错误。
- 管理面/技能详情接口提供可供前端枚举的有效引擎集合，保证 UI 能正确展示和约束用户选择。

## Capabilities

### New Capabilities
- `skill-package-validation-schema`: 以独立 schema 文件定义 skill 包合同（含 `runner.json` 与 input/parameter/output meta-schema），并作为安装/临时上传校验的统一基线。

### Modified Capabilities
- `skill-package-install`: 调整 `engines` 约束为可选，并引入 `unsupported_engines`/冲突检查/有效引擎集合语义。
- `ephemeral-skill-validation`: 与持久安装保持一致的 `engines` 可选与 `unsupported_engines` 校验规则。
- `interactive-job-api`: run 创建阶段基于有效引擎集合执行 engine 允许性校验并在违规时拒绝请求。
- `management-api-surface`: 管理接口返回可用于前端枚举的技能有效引擎集合及相关声明字段。

## Impact

- Affected code:
  - `server/services/skill_package_validator.py`
  - `server/models/*`（skill manifest / DTO）
  - `server/routers/*`（jobs / management）
  - `server/services/*`（run 前置校验、skill 元数据解析）
  - `server/assets/schemas/*`（新增 skill package / runner / input / parameter / output schema）
- Affected tests:
  - `tests/unit/test_skill_package_validator.py`
  - `tests/unit/test_jobs*.py`
  - `tests/unit/test_management*.py`
- Affected docs:
  - `docs/dev_guide.md`
  - `docs/api_reference.md`
