## 为什么要做

当前 Skill-Runner 将 `input` 固定为“上传文件路径”，`parameter` 固定为“配置参数”。
这在文件型任务上有效，但无法覆盖“业务输入本身是字符串、数组、对象”的场景。

这类数据语义上应属于 `input`（处理对象），而不是 `parameter`（执行开关/控制参数）。

## 变更目标

新增一套兼容协议：`input` 同时支持两类来源。

- 文件来源（现有能力）：从 `uploads/` 严格键匹配注入路径。
- 内联来源（新增能力）：客户端在 `POST /v1/jobs` 请求体中直接提供 `input` JSON。

同时保持已有行为不破坏：

- 旧 skill（`input` 全是文件）零改动可继续运行。
- 仍保留“文件上传后再执行”的工作流。
- 不引入全局 `Enable Inline Input` 开关。

## 变更范围

- API 请求模型：新增顶层 `input` 字段。
- schema 扩展：`input.schema.json` 支持 `x-input-source`（`file` / `inline`）。
- 执行校验：对 `input` 按来源拆分校验。
- 缓存键：纳入 inline input 哈希，避免误命中。
- 文档与测试：补充 mixed input 协议与兼容用例。
