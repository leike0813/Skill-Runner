# 输入与文件协议 (Input & File Protocol)

本文档描述当前实现下 Skill Runner 的输入、上传、产物识别与 bundle 协议。

## 1. 术语与模型

- `input`：业务输入，可混合两类来源。
  - `file`：来自上传 Zip，运行时注入为绝对路径字符串。
  - `inline`：来自 `POST /v1/jobs` 请求体的 `input` JSON 值。
- `parameter`：业务参数/配置，来自 `POST /v1/jobs` 请求体的 `parameter`。
- `artifact`：output JSON 中被 `x-type: "artifact" | "file"` 标记的文件路径字段；终态前会被统一 resolve 为 bundle 内相对路径。

## 2. `runner.json` 合同（当前实现）

最小必需字段：

```json
{
  "id": "your-skill-id",
  "execution_modes": ["auto", "interactive"]
}
```

可选覆盖声明：

```json
{
  "schemas": {
    "input": "assets/input.schema.json",
    "parameter": "assets/parameter.schema.json",
    "output": "assets/output.schema.json"
  },
  "engine_configs": {
    "gemini": "custom/gemini_settings.json"
  },
  "runtime": {
    "default_options": {
      "hard_timeout_seconds": 900,
      "execution_mode": "interactive"
    }
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
- `schemas` 不是强制显式声明；系统按以下顺序解析：
  - `runner.json.schemas.<key>`
  - 固定 fallback：`assets/<key>.schema.json`
- `engine_configs` 为可选引擎级配置覆盖声明；系统按以下顺序解析：
  - `runner.json.engine_configs.<engine>`
  - 固定 fallback 文件名：
    - `codex` -> `assets/codex_config.toml`
    - `gemini` -> `assets/gemini_settings.json`
    - `qwen` -> `assets/qwen_config.json`
    - `opencode` -> `assets/opencode_config.json`
- schema 声明失败会 warning；engine config 声明失败仅后台日志，不做用户可见 warning。
- `output` schema 必须可解析；`input` / `parameter` schema 可选，缺失时跳过对应校验。
- `runtime.default_options` 为可选 skill 默认运行参数声明：
  - 仅白名单 runtime option 键会生效；
  - 请求体 `runtime_options` 同名键优先覆盖 skill 默认值；
  - 非法默认值会被忽略，并记录 warning（不阻断执行）。

## 3. Schema 规范

### 3.1 `input.schema.json`

- 可选；存在时用于校验业务输入并构建输入上下文。
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

- 可选；存在时用于校验 `parameter` payload。
- 顶层应为 `type: "object"`。

### 3.3 `output.schema.json`

- 必需；用于结构化输出校验、run-scoped output schema materialization 与 artifact 推断。
- 顶层应为 `type: "object"`。
- 多种业务结果形态应写成顶层 object union：`{"type": "object", "oneOf": [...]}` 或 `{"type": "object", "anyOf": [...]}`。
- object union 建议每个分支使用同一个 `const` discriminator 字段，例如 `kind`。
- 支持在属性上声明：
  - `x-type: "artifact"` 或 `x-type: "file"`
  - `x-type: "artifact"` 必须声明非空 `x-role`
  - `x-role: "artifact-manifest"` 表示该字段值是产物清单 JSON 路径

## 4. 输入校验与注入流程

### 4.1 Create 阶段（`POST /v1/jobs`）

- 所有业务输入都通过请求体 `input` 提交：
  - `inline` 字段：值为业务 JSON；
  - `file` 字段：值为 `uploads/` 根下的相对路径字符串（例如 `papers/a.pdf`）。
- 预校验规则：
  - 未声明的 input key：报错；
  - file 路径必须是非空字符串、非绝对路径、且不得包含 `..`；
  - `inline` 的类型/required 按 input schema 校验。
- 旧的 `uploads/<field_name>` 严格键匹配仍保留为兼容回退，但不再是主协议。
- runtime options 合成顺序：
  - 先应用 `runner.json.runtime.default_options`（若存在且合法）；
  - 再应用请求体 `runtime_options` 覆盖；
  - 最终结果写入 `effective_runtime_options`。

### 4.2 Upload 阶段（`POST /v1/jobs/{request_id}/upload`）

- 上传 Zip 先解压到 `data/requests/{request_id}/uploads/`。
- 创建 run 时再“提升”到 `data/runs/{run_id}/uploads/`。
- Zip 包内部允许任意目录结构。
- 若请求体中已显式声明 file 输入路径，上传后系统会校验这些路径在 `uploads/` 下真实存在。

### 4.3 Workspace file bindings

当 `runtime_options.workspace.mode` 为 `reuse` 时，请求可声明 `runtime_options.workspace.file_bindings`，把同一物理 workspace 内已有文件 materialize 成当前 run 的 file input。

```json
{
  "input": {
    "artifact_file": "inputs/artifact_file/file.json"
  },
  "runtime_options": {
    "workspace": {
      "mode": "reuse",
      "request_id": "previous-request-id",
      "file_bindings": [
        {
          "input_key": "artifact_file",
          "source_request_id": "emitting-request-id",
          "source_path": "runtime/file.json",
          "target_path": "inputs/artifact_file/file.json"
        }
      ]
    }
  }
}
```

规则：

- `input[input_key]` 必须存在且等于 `target_path`；后端不会隐式改写 `input`。
- `source_request_id` 必须是同一物理 workspace 内的 succeeded request。
- `source_path` 是 workspace-relative 文件路径；`target_path` 是 uploads-relative 文件路径。
- 两类路径都禁止绝对路径、空路径、`.`、`..`、越界和目录目标。
- 同一请求内重复 `input_key` 或重复 `target_path` 会被拒绝。
- create flow 中，若声明/必需 file input 都能由 bindings 满足，请求无需 `/upload` 即可进入 queued。
- upload flow 中，Zip 先解压，bindings 随后 materialize；同 target 时 binding 覆盖 Zip 文件。
- manifest/hash 在 materialize 后计算，绑定文件内容会进入 cache key。

### 4.4 执行前混合输入构建

- `file` 字段优先按请求体 `input.<field_name>` 中声明的 `uploads/` 相对路径 resolve。
- resolve 成功后注入绝对路径字符串。
- 若请求体未显式提供该 file 字段，则回退到旧的严格键匹配：
  - 查找 `run_dir/uploads/<field_name>`
- `inline` 字段：读取 `input[field_name]` 原始 JSON 值。
- `required` 的 file 字段在“显式路径 + 兼容回退”都无法命中时会触发缺文件错误。

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

- Artifact 字段由 `output.schema.json` 中的 `x-type in {"artifact","file"}` 标记。
- `x-type: "artifact"` 必须声明非空 `x-role`；普通 role 表示字段值是单个产物路径。
- `x-role: "artifact-manifest"` 是保留 role，表示字段值是一个扁平 JSON object 清单路径，例如 `{"html": "artifacts/report.html"}`。
- manifest object 的值必须是 workspace-relative 文件路径；绝对路径、空路径、`..`、目录、缺失文件、嵌套 object/array 或非字符串值都会产生 `BUNDLE_ASSEMBLY_*` diagnostic。
- `x-filename` 已废弃，不再参与运行期校验与目标路径推断。
- `runner.json.artifacts` 若保留，仅作为兼容元数据；artifact 真源是 output JSON 中对应字段的路径值。

### 7.2 运行期校验

- 终态前系统会统一执行 artifact path resolve：
  1. 读取 output JSON 中被 `x-type` 标记的路径字段；
  2. 解析为 run 内实际文件；
  3. 若文件在 run 目录外，则执行唯一兜底移动到 run 内安全位置；
  4. 将字段值覆写为 bundle-relative path，并写回 `result.json`。
- 对 `x-role: "artifact-manifest"` 字段，系统会将 manifest 文件本身以及 manifest 内所有路径写入 `result.json.artifacts`。
- required artifact 的校验基于：
  - required 字段是否存在；
  - 以及 resolved 文件是否真实存在。
- 不再校验固定的 `artifacts/<pattern>` 文件名。
- bundle 组装时 `result.json.artifacts` 是严格合同，缺失或非法 entry 不会被静默跳过。

## 8. 结果与 Bundle

- `GET /v1/jobs/{request_id}/artifacts`：返回 resolved artifact 相对路径列表。
- `GET /v1/jobs/{request_id}/bundle`：下载普通 bundle。
  - 仅包含 `result/result.json` 与 resolved artifact 文件。
- `GET /v1/jobs/{request_id}/bundle/debug`：下载 debug bundle。
  - 保留更宽范围的运行期排障文件。
- 单文件 artifact 下载接口已废弃；统一通过 bundle / debug bundle 获取产物。
