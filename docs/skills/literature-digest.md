# literature-digest 使用说明

本文档说明如何通过 Skill Runner 调用 `literature-digest` skill。

## 支持引擎

`literature-digest` 仅允许以下引擎：
- `gemini`
- `codex`
- `iflow`

若请求中的 `engine` 不在列表内，`POST /v1/jobs` 会返回 400。

## 输入与参数

输入 schema（文件上传）：
- `md_path`（必填，扩展名 `.md`）

参数 schema（JSON）：
- `language`（可选，默认 `zh-CN`，例如 `en-US`）

## 调用流程

1) 创建任务

```json
POST /v1/jobs
{
  "skill_id": "literature-digest",
  "engine": "gemini",
  "parameter": {
    "language": "zh-CN"
  },
  "model": "gemini-3-pro-preview",
  "runtime_options": {
    "no_cache": false,
    "debug": false
  }
}
```

模型选择说明：
- 先通过 `GET /v1/engines/{engine}/models` 获取可用模型列表。
- Codex 模型使用 `model_name@reasoning_effort` 格式（例如 `gpt-5.2-codex@high`）。

返回：
```json
{
  "request_id": "uuid",
  "cache_hit": false,
  "status": "queued"
}
```

2) 上传输入文件（Zip）

Zip 内文件名必须 **严格匹配** `md_path`：

```
md_path
```

请求：
```
POST /v1/jobs/{request_id}/upload
Content-Type: multipart/form-data
file=@inputs.zip
```

3) 轮询状态

```
GET /v1/jobs/{request_id}
```

当 `status` 变为 `succeeded` 或 `failed` 时结束等待。

4) 获取结果与产物

- 结构化结果：
  ```
  GET /v1/jobs/{request_id}/result
  ```

- 产物列表：
  ```
  GET /v1/jobs/{request_id}/artifacts
  ```

- 单文件下载：
  ```
  GET /v1/jobs/{request_id}/artifacts/{artifact_path}
  ```

- bundle 下载（包含 manifest 与产物）：
  ```
  GET /v1/jobs/{request_id}/bundle
  ```

## 产物与结果约定

`output.schema.json` 要求以下字段存在（缺失即失败）：
- `digest_path`（artifact，默认 `digest.md`）
- `references_path`（artifact，默认 `references.json`）
- `provenance`（含 `generated_at`、`input_hash`、`model`）
- `warnings`（数组）
- `error`（对象或 null）

典型产物：
- `artifacts/digest.md`
- `artifacts/references.json`

## 常见错误

- **400 引擎不匹配**：`engine` 不在 `runner.json.engines` 中。
- **输入缺失**：未上传 `md_path` 文件或 Zip 内文件名不匹配。
- **输出校验失败**：缺失必填字段或 JSON 不合规，任务会标记为 `failed`。
