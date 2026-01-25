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
  "parameter": {
    "divisor": 1                 // 仅包含配置参数
  },
  "model": "gemini-2.5-pro",
  "runtime_options": {}
}
```

**关键说明**:
- **参数分离**: API 请求体中的 `parameter` 字段仅用于传递 `parameter.schema.json` 中定义的数值或配置。
- **模型字段**:
  - `model` 为顶层字段，先通过 `GET /v1/engines/{engine}/models` 获取可用模型列表。
  - **Codex** 使用 `model_name@reasoning_effort` 格式（例如 `gpt-5.2-codex@high`）。
- **运行时选项**:
  - `runtime_options` 不影响输出结果（例如 `verbose`）。
- **禁用缓存**: 设置 `runtime_options.no_cache=true` 将跳过缓存命中检查，但成功执行仍会更新缓存。
- **Debug Bundle**: 设置 `runtime_options.debug=true` 时，bundle 会打包整个 `run_dir`（含 logs/result/artifacts 等）；默认 `false` 时仅包含 `result/result.json` 与 `artifacts/**`。两者分别包含 `bundle/manifest_debug.json` 与 `bundle/manifest.json`。
- **模型校验**: `model` 必须在 `GET /v1/engines/{engine}/models` 的 allowlist 中。
- **引擎约束**: `engine` 必须包含在 skill 的 `engines` 列表中，否则直接返回 400。
- **文件输入**: 不再在创建请求中传递文件路径占位符。文件输入完全由后续的 `/upload` 接口和文件系统状态决定。
- **input.json**: 系统会将此请求保存下来（主要包含 parameter），用于审计。
- **严格校验**: 缺少 required 的输入/参数/输出字段时会标记为 failed（不会仅给 warning）。

**Response** (`RunCreateResponse`):
```json
{
  "request_id": "d290f1ee-6c54-4b01-90e6-...",
  "cache_hit": false,
  "status": "queued"
}
```

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

## 3. 引擎 (Engines)

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
