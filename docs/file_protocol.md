# 输入与文件协议 (Input & File Protocol)

本文档描述当前实现下 Skill Runner 的输入、上传、产物识别与下载协议。

## 1. 术语与模型

- `input`：业务输入，可混合两类来源。
  - `file`：来自上传 Zip，运行时注入为绝对路径字符串。
  - `inline`：来自 `POST /v1/jobs` 请求体的 `input` JSON 值。
- `parameter`：业务参数/配置，来自 `POST /v1/jobs` 请求体的 `parameter`。
- `artifact`：Skill 运行后写入 `run_dir/artifacts/` 的文件产物。

## 2. `runner.json` 合同（当前实现）

最小必需字段：

```json
{
  "id": "your-skill-id",
  "execution_modes": ["auto", "interactive"],
  "schemas": {
    "input": "assets/input.schema.json",
    "parameter": "assets/parameter.schema.json",
    "output": "assets/output.schema.json"
  }
}
```

可选引擎字段：

- `engines`：可选 allow-list。
- `unsupported_engines`：可选 deny-list。
- `effective_engines = (engines if provided else all_supported) - unsupported_engines`。

约束：

- `engines` 与 `unsupported_engines` 只能包含系统支持引擎。
- 两者不可重叠。
- `effective_engines` 不能为空。
- 旧字段 `unsupport_engine` 会被拒绝（已重命名）。

## 3. Schema 规范

### 3.1 `input.schema.json`

- 顶层应为 `type: "object"`。
- 每个属性可用 `x-input-source` 指定来源：
  - `file`（默认）
  - `inline`

示例：

```json
{
  "type": "object",
  "properties": {
    "input_file": { "type": "string", "x-input-source": "file" },
    "query": { "type": "string", "x-input-source": "inline" }
  },
  "required": ["input_file", "query"]
}
```

说明：

- `extensions` 字段允许出现在 schema 中（通过 meta-schema），但服务端当前不会基于 `extensions` 做文件后缀强校验。

### 3.2 `parameter.schema.json`

- 顶层应为 `type: "object"`。
- 用于校验 `parameter` payload。

### 3.3 `output.schema.json`

- 顶层应为 `type: "object"`。
- 支持在属性上声明：
  - `x-type: "artifact"` 或 `x-type: "file"`
  - 可选 `x-role`
  - 可选 `x-filename`

## 4. 输入校验与注入流程

### 4.1 Create 阶段（`POST /v1/jobs`）

- 仅对 `inline` 输入做预校验：
  - 未声明的 input key：报错。
  - 把 `file` 类型 key 放到 `input`：报错（提示走 `/upload`）。
  - `inline` 的类型/required 按 input schema 校验。

### 4.2 Upload 阶段（`POST /v1/jobs/{request_id}/upload`）

- 上传 Zip 先解压到 `data/requests/{request_id}/uploads/`。
- 创建 run 时再“提升”到 `data/runs/{run_id}/uploads/`。

### 4.3 执行前混合输入构建

- `file` 字段：按严格键匹配查找 `run_dir/uploads/<field_name>`。
- `inline` 字段：读取 `input[field_name]` 原始 JSON 值。
- 仅 `required` 的 file 字段缺失会触发缺文件错误。

## 5. 严格键匹配（file 输入）

规则：

1. 仅查找 `run_dir/uploads/`。
2. 文件名必须与 input 字段名完全一致（`<field_name>`）。
3. 命中后注入绝对路径字符串。
4. required file 未命中则校验失败并拒绝执行。

## 6. Prompt 上下文

- `{{ input }}`：混合输入上下文
  - file 字段：绝对路径
  - inline 字段：原始 JSON 值
- `{{ parameter }}`：参数上下文

建议在模板中显式引用：

- `{{ input.xxx }}`
- `{{ parameter.xxx }}`

## 7. Artifact 协议与推断

### 7.1 声明来源

- 若 `runner.json.artifacts` 有内容：以其为准。
- 若 `runner.json.artifacts` 缺失或为空：系统从 `output.schema.json` 自动推断：
  - 识别 `x-type in {"artifact","file"}` 的字段
  - `pattern = x-filename or 字段名`
  - `role = x-role or "output"`
  - `required = 字段名是否在 output.required`

### 7.2 运行期校验

- 运行后系统会校验 required artifacts 是否存在于 `artifacts/<pattern>`。
- 缺失 required artifact 会导致 run 失败。

## 8. 结果与下载

- `GET /v1/jobs/{request_id}/artifacts`：返回产物相对路径列表。
- `GET /v1/jobs/{request_id}/artifacts/{artifact_path}`：下载单个产物，`artifact_path` 必须以 `artifacts/` 开头且路径安全。
- `GET /v1/jobs/{request_id}/bundle`：下载 run bundle（普通或 debug 版本）。

