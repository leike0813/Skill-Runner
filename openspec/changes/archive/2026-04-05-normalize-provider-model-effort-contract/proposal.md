## Why

当前模型选择合同仍然混杂着多种历史写法：
- 新客户端开始显式传 `provider_id + model`
- 旧客户端仍通过 `model="provider/model@effort"` 或 `model="model@effort"` 传值
- 各引擎对 provider 是否必填、effort 是否可选、以及模型目录如何返回这些字段并不一致

这会同时带来三个问题：
- 请求解析路径分散在 `jobs`、lifecycle、auth orchestration 与前端表单逻辑中
- 外部前端无法依赖稳定的 `provider_id/model/supported_effort` 合同构建三级选择
- `effort` 经常只停留在请求层，没有可靠地下沉到引擎实际生效的 run-dir 配置

本次变更将模型选择统一收口为标准三元组 `provider_id + model + effort`，并在共享层保留对旧式 `provider/model@effort` 的兼容解析。

## What Changes

- 引入共享的模型选择规范化层，统一解析：
  - 新式 `provider_id + model + effort`
  - 兼容旧式 `provider/model@effort`、`provider/model`、`model@effort`
- 在各引擎 `adapter_profile.json` 中显式声明：
  - `multi_provider`
  - `canonical_provider_id`
- 单 provider 引擎（`codex`、`gemini`、`iflow`）对外固定返回 canonical provider；输入侧允许 `provider_id` 为空或任意值
- 多 provider 引擎（`claude`、`qwen`、`opencode`）要求标准输入显式带 `provider_id`；仅兼容旧式 `provider/model...` 从 `model` 推导 provider
- 模型列表接口统一返回 `provider_id`、`model`、`supported_effort`
- `effort` 空值统一解释为 `"default"`；支持 effort 的模型将 `"default"` 映射为引擎实际生效值，不支持 effort 的模型统一暴露 `["default"]`
- `opencode` 的 runtime probe 改为 `opencode models --verbose`，从 `variants` 键名导出 `supported_effort`
- E2E 提交页新增 `effort` 下拉，并作为 `provider/model/effort` 三级选择的一部分；不支持 effort 的模型保持下拉可见但禁用

## Capabilities

### Modified Capabilities
- `interactive-job-api`: run 创建请求与兼容解析改为标准三元组合同
- `management-api-surface`: 引擎模型列表输出统一为 `provider_id/model/supported_effort`
- `engine-runtime-config-layering`: effort 必须进入运行时配置分层并写入实际生效配置
- `builtin-e2e-example-client`: E2E 提交页改为 provider/model/effort 三级联动

## Impact

- 请求模型：`RunCreateRequest`、临时 run create payload
- 共享服务：`model_registry`、run execution normalization、lifecycle provider resolution
- 引擎实现：`codex`、`claude`、`qwen`、`opencode`、`gemini`、`iflow` 的 adapter profile / config 组装
- 动态探测：`opencode` models probe
- 前端：E2E run form
- 文档：API reference 与相关前端升级说明
