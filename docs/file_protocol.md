# 输入与文件协议 (Input & File Protocol)

为了清晰区分“业务输入”与“配置参数”，系统采用了严格的命名和处理协议。

## 1. 术语定义

- **Input (输入)**: 指代处理对象，可来自两种来源：
  - `file`: 上传文件并注入路径（例如：`input_file`、`source_image`）。
  - `inline`: 请求体中直接给出的 JSON 值（例如：`query`、`items`）。
- **Parameter (参数/配置)**: 指代控制逻辑的选项。例如：`temperature`、`retry_count`、`language`、`divisor`。

## 2. Schema 定义规范

在 `skills/<skill_id>/assets/runner.json` 中，必须明确区分这两类 Schema，并显式声明支持的 `engines`：

```json
{
  "engines": ["gemini", "codex"],
  "schemas": {
    "input": "assets/input.schema.json",       // 定义文件输入
    "parameter": "assets/parameter.schema.json", // 定义配置参数
    "output": "assets/output.schema.json"
  }
}
```

### `input.schema.json`
定义业务输入。每个字段可通过 `x-input-source` 指定来源：

- `file`（默认）：从 `uploads/` 目录按键名匹配文件并注入绝对路径。
- `inline`：从 `POST /v1/jobs` 请求体顶层 `input` 读取 JSON 值。

对于 `file` 字段，可用 `extensions` 限制文件类型。

```json
{
  "type": "object",
  "properties": {
    "input_file": {
      "type": "string",
      "description": "Path to the data file",
      "x-input-source": "file",
      "extensions": [".txt", ".md"] 
    },
    "query": {
      "type": "string",
      "x-input-source": "inline"
    }
  },
  "required": ["input_file", "query"]
}
```

### `parameter.schema.json`
定义纯数值或字符串配置。

```json
{
  "type": "object",
  "properties": {
    "divisor": { 
      "type": "integer", 
      "default": 1 
    }
  }
}
```

## 3. 严格键匹配机制 (Strict Key-Matching, 仅 file 输入)

这是为了解决文件上传不确定性而引入的核心机制。

**规则**:
当适配器处理 `x-input-source=file` 的 `input` 字段（例如 `input_file`）时：
1. 它**仅**检查运行目录下的 `uploads/` 文件夹。
2. 它查找是否存在文件名**完全等于**字段名（`input_file`）的文件。
3. **如果找到**: 适配器会生成该文件的**绝对路径**，并将其作为该字段的值注入 `{{ input }}` 上下文。
4. **如果未找到**: **直接报错**。

**示例**:
- Schema 定义了 `input_file`。
- API 请求 (`POST /v1/jobs`): 可包含 inline 输入，例如 `{ "input": {"query": "hello"} }`。
- 用户上传了 Zip，解压后包含文件 `uploads/input_file`。
- **最终执行值**: `/abs/path/to/runs/xxx/uploads/input_file`。
- **注意**: 如果 `uploads/input_file` 不存在，任务将直接失败。

## 4. Prompt 上下文与 Jinja2

在 `GeminiAdapter` 的默认 Prompt 模板中，这两个上下文被分开渲染：

```jinja2
# Inputs
{% for key, value in input.items() %}
- {{ key }}: {{ value }}
{% endfor %}

# Parameters
{% for key, value in parameter.items() %}
- {{ key }}: {{ value }}
{% endfor %}
```

- `{{ input }}`: 包含解析后的 mixed input：
  - file 字段值是绝对路径字符串
  - inline 字段值是原始 JSON 值
- `{{ parameter }}`: 包含所有的配置值。

在 `SKILL.md` 中，你也应该使用特定命名空间引用变量：
- 引用 file 输入: `{{ input.input_file }}`
- 引用 inline 输入: `{{ input.query }}`
- 引用参数: `{{ parameter.divisor }}`

## 5. 自定义 Prompt 模版 (Custom Prompt Templates)

虽然系统提供了通用的默认模版，但在某些场景下（如消除歧义、构造特定 JSON 结构），Skill 开发者需要在 `runner.json` 中提供自定义模版。

### 场景 A：消除歧义 (Disambiguation)
例如 `file-size-compare` 技能，需要明确区分“第一个文件”和“第二个文件”。通用模版的 KV 列表形式可能无法准确传达这种顺序关系。

**runner.json 配置**:
```json
{
  "entrypoint": {
    "prompts": {
      "gemini": "调用file-size-compare技能，第一个文件是`{{ input.file_src }}`，第二个文件是`{{ input.file_dst }}`"
    }
  }
}
```
通过这种方式，可以将 Input Schema 中的特定字段“钉死”在 Prompt 的特定语义位置。

### 场景 B：构造特定结构 (Specific Structure)
例如 `literature-digest` 技能，可能要求输入必须是一个特定的 JSON 结构。

**runner.json 配置**:
```json
{
  "entrypoint": {
    "prompts": {
      "gemini": "请调用literature-digest技能，输入如下：\n```json\n{\n  \"md_path\": \"{{ input.md_path }}\",\n  \"language\": \"{{ parameter.language }}\"\n}\n```"
    }
  }
}
```
这允许 Runner 适配各种对输入格式有严格要求的存量 Skill，而无需修改 Skill 本身的代码。

## 6. 运行时依赖定义 (Runtime Dependencies)

为了支持基于容器或 `uv` 的动态环境创建，Skill 需要在 `runner.json` 中声明其运行时依赖。

**runner.json 配置**:
```json
{
  "runtime": {
    "language": "python",
    "version": "3.11",
    "dependencies": [
      "pandas>=2.0.0",
      "numpy",
      "scipy"
    ]
  }
}
```

**机制**:
1. 当 Job Orchestrator 准备执行环境时，会读取 `runtime.dependencies` 列表。
2. 适配器（如 `GeminiAdapter` 或未来的 `DockerAdapter`）将使用这些依赖构建临时的隔离环境（例如使用 `uv run --with pandas --with numpy ...`）。
3. 随后在此环境中执行 Skill 逻辑（如生成 Python 脚本）。

## 7. Output Schema & Artifacts

为了让 Runner 能够自动识别 Skill 生成的文件（Artifacts）并进行后续处理（如 Skill Patching），必须在 `output.schema.json` 中明确标识文件路径字段。

**规范**:
在 Schema 的 Property 中添加 `x-type: "artifact"` 字段。
此外，建议使用 `x-role` 和 `x-filename` 进一步明确 Artifact 的属性，从而免去在 `runner.json` 中重复定义。

**output.schema.json 示例**:
```json
{
  "type": "object",
  "properties": {
    "digest_path": {
      "type": "string",
      "description": "Path to the generated digest file",
      "x-type": "artifact",
      "x-role": "digest",             // Optional: Semantic role (default: "output")
      "x-filename": "digest.md"       // Optional: Expected filename (default: property key)
    },
    "metadata": {
      "type": "object",
      "description": "Validation metadata (Required, but not a file)"
    }
  },
  "required": ["digest_path", "metadata"]
}
```

**机制**:
1. **Artifact 扫描**: 系统加载 Skill 时，会扫描 `output.schema.json`。
2. **自动注册**: 所有标记为 `x-type: "artifact"` 的字段会被自动注册到 Skill Manifest 的 artifact 列表中。
   - `role`: 取自 `x-role`，若未定义则默认为 `"output"`。
   - `pattern`: 取自 `x-filename`，若未定义则默认为字段名 (Key)。
3. **Skill Patching**: 执行时，适配器会将这些字段注入到 `SKILL.md` 的输出指令中。
