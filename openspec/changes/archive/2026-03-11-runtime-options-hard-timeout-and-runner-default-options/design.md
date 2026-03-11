## Overview

本 change 在不新增执行语义的前提下，做两项契约收口：

1. `hard_timeout_seconds` 进入正式 runtime options 合同；
2. `runner.json.runtime.default_options` 进入默认值合成链路。

设计重点：
- 默认值合成仅改变 `effective_runtime_options`，请求 `runtime_options` 仍代表用户请求侧输入（经现有校验归一化）。
- 默认值无效时采用“忽略并告警”，不阻断安装、上传或执行。
- create 与 upload 两条路径使用同一 helper，避免行为漂移。

## Runtime Option Composition

统一合成顺序：

1. 读取 skill 默认值：`runner.json.runtime.default_options`（可选）
2. 过滤默认值：
   - 键不在 runtime allowlist -> 忽略并告警
   - 值不满足对应校验 -> 忽略并告警
3. 合成：`merged = {**skill_defaults_valid, **request_runtime_options}`
4. 对合成结果执行现有 `OptionsPolicy.validate_runtime_options`
5. 得到 `effective_runtime_options`

其中请求侧键始终优先，skill 默认值只在请求未显式传入该键时生效。

## Warning Model

默认值被忽略时统一产出 warning payload：

- code: `SKILL_RUNTIME_DEFAULT_OPTION_IGNORED`
- detail: 包含 `skill_id/key/reason` 摘要

传播策略：
- 创建/上传阶段写结构化日志；
- 启动执行时通过内部 `options` 注入 warning payload；
- 生命周期用既有 warning 收敛逻辑写入 state warnings 与 diagnostic.warning 事件。

## Create/Upload Integration

### Installed skill (`POST /v1/jobs`)

- create 时已有 skill manifest，可直接完成默认值合成；
- `effective_runtime_options` 用合成结果；
- warning payload 透传给 run lifecycle。

### Temp upload (`POST /v1/jobs` + `/upload`)

- create 阶段尚无 skill manifest：仅校验请求 runtime options；
- upload 阶段拿到 manifest 后，重算 `effective_runtime_options` 并持久化；
- 后续缓存键、run 启动、lifecycle warning 与 installed skill 行为保持一致。

## Contract Changes

- `skill_runner_manifest.schema.json`：
  - 新增 `runtime` 对象结构；
  - `runtime.default_options` 声明为 object（键值对）。
- `options_policy`：
  - allowlist 纳入 `hard_timeout_seconds`；
  - 新增正整数校验。

## Non-goals

- 不改管理 UI/E2E 表单预填。
- 不新增 runtime option 键集合（仅开放已有能力）。
- 不更改 cache 策略、交互状态机和引擎适配行为。
