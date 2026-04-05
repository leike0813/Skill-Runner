## Overview

本次设计将“模型选择”定义为独立于鉴权的共享合同，统一产出：
- `provider_id`
- `model`
- `requested_effort`
- `effective_effort`

所有入口都先做规范化，再进入 run 创建、lifecycle、auth orchestration、以及引擎配置写入。

## Design Decisions

### 1. 共享规范化层是唯一解析入口

历史上 `provider/model@effort` 的解析散落在多个代码路径里。本次统一由共享规范化层完成：
- 输入层允许新式三元组
- 同时兼容旧式 `provider/model@effort`
- 内部状态统一为规范化后的 `provider_id + model + effort`

兼容只存在于输入侧。对外返回、存储和后续处理都不继续传播旧式拼接字符串语义。

### 2. provider 是否必填由 adapter profile 声明，而不是 auth helper 推断

`provider_aware_auth.py` 只保留鉴权层职责；模型选择是否需要 provider 改由 adapter profile 声明：
- `multi_provider=false` 时，运行时始终收口到 canonical provider
- `multi_provider=true` 时，标准输入必须带 provider；仅兼容旧式 `provider/model...` 可从 `model` 字段推导

这样单 provider 引擎不再被要求显式传 provider，同时多 provider 引擎也不会再依赖零散特判。

### 3. effort 语义分为“请求值”和“生效值”

输入层统一接受：
- `effort="" | null` => `requested_effort="default"`

规范化后区分：
- `requested_effort`: 客户端提交的语义值
- `effective_effort`: 对支持 effort 的模型真正写入配置的值

规则：
- 不支持 effort 的模型统一返回 `supported_effort=["default"]`，`effective_effort=None`
- 支持 effort 的模型：
  - `requested_effort="default"` 时，优先映射到 `medium`
  - 若该模型不包含 `medium`，退回其首个支持项，保证 `"default"` 总能落到一个真实生效值

### 4. runtime_model 只作为内部兼容字段

部分引擎的运行时配置仍需要 `provider/model`：
- `opencode`
- `claude` custom provider

因此规范化层额外给出 `runtime_model`，供运行目录配置组装使用。
但对外标准字段仍只有：
- `provider_id`
- `model`
- `supported_effort`

`runtime_model` 不是公开 API 的一等合同。

### 5. E2E 表单固定为三级联动，不因模型能力抖动布局

E2E run form 改为固定的三段式选择：
- provider
- model
- effort

其中 `effort`：
- 始终可见
- 不支持 effort 的模型显示固定 `default` 且禁用
- 支持 effort 的模型启用下拉，并提供 `default + supported_effort`

这避免因模型切换导致布局抖动，同时让外部前端直接复用统一合同。

## Affected Specs

- `interactive-job-api`
- `management-api-surface`
- `engine-runtime-config-layering`
- `builtin-e2e-example-client`
