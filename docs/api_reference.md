# API 接口文档 (API Reference)

本文档描述 Skill Runner 提供的 RESTful API 接口。

## Base URL
默认为 `http://localhost:8000` (取决于部署配置)。
建议使用版本化前缀：`/v1`。

示例：
`http://localhost:8000/v1`

---

## 1. 技能 (Skills)

### 获取技能列表
`GET /v1/skills`

返回当前系统已加载的所有技能定义。

**Response** (`List[SkillManifest]`):
```json
[
  {
    "id": "demo-prime-number",
    "name": "Prime Number Generator",
    "version": "1.0.0",
    "schemas": { ... }
  }
]
```

### 获取特定技能
`GET /v1/skills/{skill_id}`

**Parameters**:
- `skill_id` (path): 技能的唯一标识符。

**Response** (`SkillManifest`):
```json
{
  "id": "demo-prime-number",
  "description": "Calculates prime numbers",
  ...
}
```

### 上传并安装/更新技能包（异步）
`POST /v1/skill-packages/install`

上传一个 Zip 格式的技能包，由服务端异步完成校验与安装（或更新）。

**Request**:
- `Content-Type`: `multipart/form-data`
- `file`: 技能 Zip 包（二进制）

**Response** (`SkillInstallCreateResponse`):
```json
{
  "request_id": "f91ccf7e-52c5-42aa-8e64-6f4a3e1b7a4c",
  "status": "queued"
}
```

### 查询技能包安装状态
`GET /v1/skill-packages/{request_id}`

**Response** (`SkillInstallStatusResponse`):
```json
{
  "request_id": "f91ccf7e-52c5-42aa-8e64-6f4a3e1b7a4c",
  "status": "succeeded",
  "created_at": "2026-02-10T08:30:00.123456",
  "updated_at": "2026-02-10T08:30:02.654321",
  "skill_id": "literature-digest",
  "version": "1.2.0",
  "action": "update",
  "error": null
}
```

**技能包校验规则（服务端）**:
- Zip 内必须且只能有一个顶层目录（该目录名即 `skill_id`）。
- 必须包含以下文件：
  - `SKILL.md`
  - `assets/runner.json`
  - `assets/input.schema.json`
  - `assets/parameter.schema.json`
  - `assets/output.schema.json`
- `SKILL.md` frontmatter 的 `name`、`assets/runner.json` 的 `id`、顶层目录名必须完全一致。
- `runner.json` 必须包含非空 `engines` 列表。
- `runner.json` 必须包含非空 `artifacts` 合同。
- `runner.json` 必须包含可解析的 `version`。

**更新规则**:
- 若 `skill_id` 已存在，则只允许严格升版（`new_version > installed_version`）。
- 不允许降级或同版本覆盖。
- 更新时旧版本会归档到 `skills/.archive/{skill_id}/{old_version}/`。
- 若目标归档路径已存在，则更新失败并保持现有技能不变。

---

## 2. 任务 (Jobs)

### 创建任务 (Create Job)
`POST /v1/jobs`

创建一个新的技能执行实例。

**Request Body** (`RunCreateRequest`):
```json
{
  "skill_id": "demo-prime-number",
  "engine": "gemini",          // 可选: "gemini" / "codex" / "iflow" (默认: codex)
  "input": {
    "query": "some inline input payload"
  },
  "parameter": {
    "divisor": 1                 // 仅包含配置参数
  },
  "model": "gemini-2.5-pro",
  "runtime_options": {}
}
```

**关键说明**:
- **输入分离（Mixed Input）**:
  - 顶层 `input` 用于传递业务输入（可为 string/array/object）。
  - 对 `input.schema.json` 中 `x-input-source=inline` 的字段，值直接来自请求体 `input`。
  - 对 `x-input-source=file`（或未声明，默认 file）的字段，值来自后续 `/upload` 上传并注入为文件路径。
- **参数分离**: API 请求体中的 `parameter` 字段仅用于传递 `parameter.schema.json` 中定义的数值或配置。
- **模型字段**:
  - `model` 为顶层字段，先通过 `GET /v1/engines/{engine}/models` 获取可用模型列表。
  - **Codex** 使用 `model_name@reasoning_effort` 格式（例如 `gpt-5.2-codex@high`）。
- **运行时选项**:
  - `runtime_options` 不影响输出结果（例如 `verbose`）。
- **禁用缓存**: 设置 `runtime_options.no_cache=true` 将跳过缓存命中检查，但成功执行仍会更新缓存。
- **Debug Bundle**: 设置 `runtime_options.debug=true` 时，bundle 会打包整个 `run_dir`（含 logs/result/artifacts 等）；默认 `false` 时仅包含 `result/result.json` 与 `artifacts/**`。两者分别包含 `bundle/manifest_debug.json` 与 `bundle/manifest.json`。
- **临时 Skill 调试保留**: `runtime_options.debug_keep_temp=true` 仅用于 `/v1/temp-skill-runs`，表示终态后不立即删除临时 skill 包与解压目录。
- **模型校验**: `model` 必须在 `GET /v1/engines/{engine}/models` 的 allowlist 中。
- **引擎约束**: `engine` 必须包含在 skill 的 `engines` 列表中，否则直接返回 400。
- **文件输入**: file 类型 input 仍由 `/upload` 接口提供。
- **input.json**: 系统会将请求保存下来（包含 `input` 与 `parameter`），用于审计。
- **严格校验**: 缺少 required 的输入/参数/输出字段时会标记为 failed（不会仅给 warning）。
- **并发保护**: 当执行队列已满时，`POST /v1/jobs` 或 `POST /v1/jobs/{request_id}/upload` 会返回 `429`。

**Response** (`RunCreateResponse`):
```json
{
  "request_id": "d290f1ee-6c54-4b01-90e6-...",
  "cache_hit": false,
  "status": "queued"
}
```

**错误码补充**:
- `429`: 全局执行队列已满，请稍后重试。

### 查询状态 (Get Status)
`GET /v1/jobs/{request_id}`

**Response** (`RequestStatusResponse`):
```json
{
  "request_id": "d290f1ee-6c54-4b01-90e6-...",
  "status": "succeeded",
  "skill_id": "demo-prime-number",
  "engine": "gemini",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:01:00Z",
  "warnings": [],
  "error": null
}
```

### 上传文件 (Upload File)
`POST /v1/jobs/{request_id}/upload`

为指定的 Request 上传输入文件。系统仅接受 Zip 格式的压缩包。

**Request**:
- `Content-Type`: `multipart/form-data`
- `file`: 二进制 Zip 文件。

**行为**:
- 系统会将 Zip 解压到 `data/requests/{request_id}/uploads/`。
- **Strict Key-Matching**: 解压后的文件名必须与 Schema 定义的 Input Key 一致（例如 `input_file`），否则在运行时会报错。

**Response** (`RunUploadResponse`):
```json
{
  "request_id": "...",
  "cache_hit": false,
  "extracted_files": ["input_file", "data.csv"]
}
```

**错误码补充**:
- `429`: 全局执行队列已满，请稍后重试。

### 获取结果 (Get Result)
`GET /v1/jobs/{request_id}/result`

**Response** (`RunResultResponse`):
```json
{
  "request_id": "d290f1ee-6c54-4b01-90e6-...",
  "result": {
    "status": "success",
    "data": { ... },
    "artifacts": ["artifacts/report.md"],
    "validation_warnings": [],
    "error": null
  }
}
```

### 获取产物清单 (Get Artifacts)
`GET /v1/jobs/{request_id}/artifacts`

**Response** (`RunArtifactsResponse`):
```json
{
  "request_id": "d290f1ee-6c54-4b01-90e6-...",
  "artifacts": ["artifacts/report.md"]
}
```

### 下载单个产物 (Download Artifact)
`GET /v1/jobs/{request_id}/artifacts/{artifact_path}`

**说明**:
- `artifact_path` 必须以 `artifacts/` 开头。
- 返回 `Content-Disposition` 以附件形式下载目标文件。

### 下载 Bundle (Get Bundle)
`GET /v1/jobs/{request_id}/bundle`

**Response**:
- 直接返回 Bundle Zip 文件（`Content-Type: application/zip`）
- `Content-Disposition` 中的文件名为 `run_bundle.zip`（debug=false）或 `run_bundle_debug.zip`（debug=true）

**说明**:
- Bundle 内包含运行产物与 `bundle/manifest.json`；debug=true 时会额外包含 logs 等调试文件，并使用 `bundle/manifest_debug.json`。

### 获取日志 (Get Logs)
`GET /v1/jobs/{request_id}/logs`

**Response** (`RunLogsResponse`):
```json
{
  "request_id": "d290f1ee-6c54-4b01-90e6-...",
  "prompt": "...",
  "stdout": "...",
  "stderr": "..."
}
```

### 清理运行记录 (Cleanup Runs)
`POST /v1/jobs/cleanup`

**Response** (`RunCleanupResponse`):
```json
{
  "runs_deleted": 42,
  "requests_deleted": 42,
  "cache_entries_deleted": 42
}
```

---

## 3. 临时技能运行 (Temporary Skill Runs)

该组接口用于“上传临时 skill 包并执行一次任务”，不会安装到持久 `skills/` 目录，也不会被 `/v1/skills` 发现。

### 创建临时运行请求
`POST /v1/temp-skill-runs`

**Request Body** (`TempSkillRunCreateRequest`):
```json
{
  "engine": "gemini",
  "parameter": {},
  "model": "gemini-2.5-pro",
  "runtime_options": {
    "debug_keep_temp": false
  }
}
```

**Response** (`TempSkillRunCreateResponse`):
```json
{
  "request_id": "2fd0a860-a560-4f2d-8c91-2d1d65f6a4f1",
  "status": "queued"
}
```

### 上传临时 Skill 包并启动运行
`POST /v1/temp-skill-runs/{request_id}/upload`

**Request**:
- `Content-Type`: `multipart/form-data`
- `skill_package`: 必填，临时 skill zip 包
- `file`: 可选，输入文件 zip（与 `/v1/jobs/{request_id}/upload` 相同格式）

**Response** (`TempSkillRunUploadResponse`):
```json
{
  "request_id": "2fd0a860-a560-4f2d-8c91-2d1d65f6a4f1",
  "status": "queued",
  "extracted_files": ["input_file"]
}
```

**错误码**:
- `400`: 包结构/元数据校验失败、引擎不匹配、请求已启动等。
- `404`: `request_id` 不存在。
- `429`: 全局执行队列已满。
- `500`: 内部错误。

### 查询临时运行状态
`GET /v1/temp-skill-runs/{request_id}`

响应结构与 `GET /v1/jobs/{request_id}` 保持一致（`RequestStatusResponse`）。

### 查询临时运行结果/产物/Bundle/日志
- `GET /v1/temp-skill-runs/{request_id}/result`
- `GET /v1/temp-skill-runs/{request_id}/artifacts`
- `GET /v1/temp-skill-runs/{request_id}/bundle`
- `GET /v1/temp-skill-runs/{request_id}/artifacts/{artifact_path}`
- `GET /v1/temp-skill-runs/{request_id}/logs`

语义与 `/v1/jobs/*` 对齐，但作用范围仅限临时 skill 的这次请求。
另外，临时 skill 运行固定绕过缓存（不读 cache，也不回写 cache）。

### 临时 Skill 包校验规则（严格）
- Zip 必须且只能有一个顶层目录（顶层目录名即 `skill_id`）。
- 禁止 zip-slip/绝对路径条目（包含 `..`、绝对路径、盘符前缀等）。
- 必须包含并可解析：
  - `SKILL.md`
  - `assets/runner.json`
  - `runner.json.schemas` 指向的 `input` / `parameter` / `output` 三个 schema 文件
- 身份一致性：顶层目录名、`runner.json.id`、`SKILL.md` frontmatter `name` 必须一致。
- 元数据约束：`runner.json.engines` 与 `runner.json.artifacts` 必须非空。
- 包大小限制：受 `TEMP_SKILL_PACKAGE_MAX_BYTES` 控制（默认 20MB）。

### 生命周期与清理
- 临时 skill 包与解压目录默认在终态（`succeeded`/`failed`/`canceled`）后立即清理。
- `runtime_options.debug_keep_temp=true` 时，跳过立即清理，仅保留用于调试。
- 若立即清理失败，仅记录 warning，不影响终态；由后台定时清理兜底。

---

## 4. 引擎 (Engines)

### 获取引擎列表
`GET /v1/engines`

**Response** (`EnginesResponse`):
```json
{
  "engines": [
    {"engine": "codex", "cli_version_detected": "0.89.0"},
    {"engine": "gemini", "cli_version_detected": "0.25.2"},
    {"engine": "iflow", "cli_version_detected": "0.5.2"}
  ]
}
```

### 获取引擎模型列表
`GET /v1/engines/{engine}/models`

**Response** (`EngineModelsResponse`):
```json
{
  "engine": "codex",
  "cli_version_detected": "0.89.0",
  "snapshot_version_used": "0.89.0",
  "source": "pinned_snapshot",
  "fallback_reason": null,
  "models": [
    {
      "id": "gpt-5.2-codex",
      "display_name": "GPT-5.2 Codex",
      "deprecated": false,
      "notes": "pinned snapshot",
      "supported_effort": ["low", "medium", "high", "xhigh"]
    }
  ]
}
```
