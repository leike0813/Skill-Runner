# API 接口文档 (API Reference)

本文档描述 Skill Runner 提供的 RESTful API 接口。

## Base URL
默认为 `http://localhost:8000` (取决于部署配置)。
建议使用版本化前缀：`/v1`。

示例：
`http://localhost:8000/v1`

---

## 0. 管理 API（Management，推荐）
<a id="management-api-recommended"></a>

`/v1/management/*` 提供前端无关的统一管理契约，适用于内置 UI 与外部前端（如插件 WebView）复用。

### Skill 管理
- `GET /v1/management/skills`：技能摘要列表（`id/name/version/engines/unsupport_engine/effective_engines/health`）
- `GET /v1/management/skills/{skill_id}`：技能详情（额外包含 `schemas/entrypoints/files/execution_modes`）
- `GET /v1/management/skills/{skill_id}/schemas`：返回 `input/parameter/output` schema 内容（用于动态表单构建）

### Engine 管理
- `GET /v1/management/engines`：引擎摘要列表（`engine/cli_version/auth_ready/sandbox_status/models_count`）
- `GET /v1/management/engines/{engine}`：引擎详情（额外包含 `models/upgrade_status/last_error`）

### Run 管理（对话窗口）
- `GET /v1/management/runs`：运行摘要列表（支持 `limit`）
- `GET /v1/management/runs/{request_id}`：会话状态（含 `pending_interaction_id`、`interaction_count`、`recovery_state/recovered_at/recovery_reason`）
- `GET /v1/management/runs/{request_id}/files`：文件树
- `GET /v1/management/runs/{request_id}/file?path=...`：文件预览
- `GET /v1/management/runs/{request_id}/events`：SSE 实时输出（复用 jobs 事件语义）
- `GET /v1/management/runs/{request_id}/pending`：查询待决交互
- `POST /v1/management/runs/{request_id}/reply`：提交交互回复
- `POST /v1/management/runs/{request_id}/cancel`：取消运行

说明：
- 管理 API 是推荐的前端消费面。
- 现有 `/v1/skills*`、`/v1/engines*`、`/v1/jobs*`、`/v1/temp-skill-runs*` 保持兼容，用于执行链路与存量调用。

---

## 1. 技能 (Skills)

### 获取技能列表
`GET /v1/skills`

返回当前系统已加载的所有技能定义。

说明：
- 仅返回“有效安装结构”的技能目录（至少包含 `SKILL.md` 与 `assets/runner.json`）。
- 新接入前端建议优先使用 `GET /v1/management/skills`（该接口保留执行域原始语义）。

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
- `input/parameter/output` schema 会在上传阶段执行服务端 meta-schema 预检：
  - `input.schema.json` 的 `x-input-source` 仅允许 `file` / `inline`；
  - `output.schema.json` 的 `x-type` 仅允许 `artifact` / `file`；
  - 三个 schema 需满足对象型 JSON Schema 基本结构约束。
- `SKILL.md` frontmatter 的 `name`、`assets/runner.json` 的 `id`、顶层目录名必须完全一致。
- `runner.json.engines` 为可选字段；缺失时默认按系统支持的全部引擎处理。
- `runner.json.unsupport_engine` 为可选字段；用于声明显式不支持引擎。
- 若 `engines` 与 `unsupport_engine` 同时存在，二者不允许重复；计算后的有效引擎集合必须非空。
- `runner.json` 必须包含非空 `execution_modes` 列表，且值仅允许 `auto` / `interactive`。
- `runner.json` 的 `artifacts` 可选；若提供，必须为数组。  
  若未提供，服务端会基于 `output.schema.json` 中的 artifact 声明推导运行时产物合同。
- `runner.json` 必须包含可解析的 `version`。

**更新规则**:
- 若 `skill_id` 已存在，则只允许严格升版（`new_version > installed_version`）。
- 不允许降级或同版本覆盖。
- 更新时旧版本会归档到 `skills/.archive/{skill_id}/{old_version}/`。
- 若目标归档路径已存在，则更新失败并保持现有技能不变。
- 若目录已存在但不是有效已安装结构（例如缺失 `assets/runner.json`），会被视为“无已安装版本”，并先移动到 `skills/.invalid/` 后按全新安装处理。
- 安装/更新落地前，系统会清理技能包内名称精确为 `.git` 的文件或目录；非 `.git` 的隐藏文件（如 `.gitignore`、`.github/`）不会被该规则删除。

---

## 2. 任务 (Jobs)

说明：
- `/v1/jobs*` 继续作为执行域 API 保持兼容。
- 前端管理/对话窗口场景建议迁移到 `/v1/management/runs*`。

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
  - **iFlow 运行时默认配置（托管环境）**：若未提供 `~/.iflow/settings.json`，服务会写入最小可用默认值：
    - `selectedAuthType = "oauth-iflow"`
    - `baseUrl = "https://apis.iflow.cn/v1"`
- **运行时选项**:
  - `runtime_options` 不影响输出结果（例如 `verbose`）。
  - `runtime_options.execution_mode` 支持 `auto`（默认）与 `interactive`。
  - 会话超时统一键：`runtime_options.session_timeout_sec`（默认 `1200`）。
  - `interactive` 下可设置 `runtime_options.interactive_require_user_reply`：
    - `true`（默认）：严格等待用户回复。
    - `false`：等待超时后自动决策并继续执行。
  - `interactive` 模式下会先进行引擎恢复能力探测，并写入 `interactive_profile.kind`：
    - `resumable`: 等待阶段使用持久化会话句柄恢复。
    - `sticky_process`: 进入驻留等待路径，按 `session_timeout_sec` 计算 `wait_deadline_at`。
  - 引擎执行启用硬超时，默认 `1200s`（环境变量 `SKILL_RUNNER_ENGINE_HARD_TIMEOUT_SECONDS` 可覆盖）。
  - 超时后会终止子进程并将 run 置为 `failed`（错误码 `TIMEOUT`）。
- **缓存策略**:
  - 设置 `runtime_options.no_cache=true` 将跳过缓存命中检查。
  - `runtime_options.execution_mode=interactive` 时，系统会跳过缓存命中，且不会写入 `cache_entries`。
- **Debug Bundle**: 设置 `runtime_options.debug=true` 时，bundle 会打包整个 `run_dir`（含 logs/result/artifacts 等）；默认 `false` 时仅包含 `result/result.json` 与 `artifacts/**`。两者分别包含 `bundle/manifest_debug.json` 与 `bundle/manifest.json`。
- **临时 Skill 调试保留**: `runtime_options.debug_keep_temp=true` 仅用于 `/v1/temp-skill-runs`，表示终态后不立即删除临时 skill 包与解压目录。
- **模型校验**: `model` 必须在 `GET /v1/engines/{engine}/models` 的 allowlist 中。
- **引擎约束**: `engine` 必须包含在 skill 的有效引擎集合中（`effective_engines = (engines 或 全量支持引擎) - unsupport_engine`），否则返回 400（`SKILL_ENGINE_UNSUPPORTED`）。
- **模式准入约束**: 请求的 `runtime_options.execution_mode` 必须包含在 skill 的 `execution_modes` 声明中，否则返回 400（`SKILL_EXECUTION_MODE_UNSUPPORTED`）。
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
- `SKILL_ENGINE_UNSUPPORTED`（HTTP 400）: Skill 未声明支持请求的 `engine`。
- `SKILL_EXECUTION_MODE_UNSUPPORTED`（HTTP 400）: Skill 未声明支持请求的 `execution_mode`。

### 查询状态 (Get Status)
`GET /v1/jobs/{request_id}`

**Response** (`RequestStatusResponse`):
```json
{
  "request_id": "d290f1ee-6c54-4b01-90e6-...",
  "status": "waiting_user",
  "skill_id": "demo-prime-number",
  "engine": "gemini",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:01:00Z",
  "pending_interaction_id": 12,
  "interaction_count": 3,
  "recovery_state": "recovered_waiting",
  "recovered_at": "2026-02-16T00:05:00Z",
  "recovery_reason": "resumable_waiting_preserved",
  "auto_decision_count": 0,
  "last_auto_decision_at": null,
  "warnings": [],
  "error": null
}
```

说明：
- `waiting_user` 为非终态，客户端应按 pending/reply 流程推进，而不是直接结束。
- `pending_interaction_id` 为空表示当前没有待决交互。
- `interaction_count` 为当前 request 已记录的交互轮次计数。
- `recovery_state` 取值：`none | recovered_waiting | failed_reconciled`。
- `failed_reconciled` 常见错误码：`SESSION_RESUME_FAILED`、`INTERACTION_PROCESS_LOST`、`ORCHESTRATOR_RESTART_INTERRUPTED`。

### 查询待决交互 (Get Pending Interaction)
`GET /v1/jobs/{request_id}/interaction/pending`

返回当前待用户答复的问题（若存在）。

**Response** (`InteractionPendingResponse`):
```json
{
  "request_id": "d290f1ee-6c54-4b01-90e6-...",
  "status": "waiting_user",
  "pending": {
    "interaction_id": 12,
    "kind": "choose_one",
    "prompt": "请选择执行策略",
    "options": [{"label": "继续", "value": "continue"}],
    "ui_hints": {"widget": "radio"},
    "default_decision_policy": "engine_judgement"
  }
}
```

无待决问题时返回 `pending: null`，并保留当前状态。
`kind` 当前支持：`choose_one`、`confirm`、`fill_fields`、`open_text`、`risk_ack`。

### 提交交互回复 (Reply Interaction)
`POST /v1/jobs/{request_id}/interaction/reply`

**Request Body** (`InteractionReplyRequest`):
```json
{
  "interaction_id": 12,
  "response": "继续执行",
  "idempotency_key": "req-12-reply-1"
}
```

**Response** (`InteractionReplyResponse`):
```json
{
  "request_id": "d290f1ee-6c54-4b01-90e6-...",
  "status": "queued",
  "accepted": true
}
```

说明：
- `status` 可能为 `queued` 或 `running`：
  - `resumable` 路径通常回到 `queued` 等待恢复执行；
  - `sticky_process` 路径维持进程槽位并回到 `running`。

**错误语义**:
- `400`: 当前请求不是 interactive 模式（`runtime_options.execution_mode != interactive`）。
- `404`: `request_id` 或 `run` 不存在。
- `409`: 非 `waiting_user` 状态提交、`interaction_id` 过期/不匹配、或 `idempotency_key` 冲突。
- `SESSION_RESUME_FAILED`: `resumable` 路径下无法提取/使用会话句柄（Codex `thread_id`、Gemini `session_id`、iFlow `session-id`）。
- `INTERACTION_WAIT_TIMEOUT`: `interactive_require_user_reply=true` 且 `sticky_process` 等待超时（超过 `wait_deadline_at`）。
- `INTERACTION_PROCESS_LOST`: `sticky_process` 等待期检测到进程绑定丢失。

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

### 获取日志事件流 (SSE)
`GET /v1/jobs/{request_id}/events`

返回 `text/event-stream`，用于实时增量消费 stdout/stderr 与状态变化。

**Query 参数**:
- `stdout_from`（可选，默认 `0`）：stdout 起始 offset。
- `stderr_from`（可选，默认 `0`）：stderr 起始 offset。

**事件类型**:
- `snapshot`：首帧快照，字段：`status`, `stdout_offset`, `stderr_offset`, `pending_interaction_id?`
- `stdout`：stdout 增量，字段：`from`, `to`, `chunk`
- `stderr`：stderr 增量，字段：`from`, `to`, `chunk`
- `status`：状态变化，字段：`status`, `updated_at?`, `pending_interaction_id?`
- `heartbeat`：保活事件，字段：`ts`
- `end`：连接结束，字段：`reason`（`waiting_user` 或 `terminal`）

**重连约定**:
- 客户端记录最近一条 `stdout/stderr` 事件的 `to`。
- 重连时将该值带回 `stdout_from/stderr_from`，服务端仅推送未消费区间。

### 取消运行 (Cancel Run)
`POST /v1/jobs/{request_id}/cancel`

**Response** (`CancelResponse`):
```json
{
  "request_id": "d290f1ee-6c54-4b01-90e6-...",
  "run_id": "run-123",
  "status": "canceled",
  "accepted": true,
  "message": "Cancel request accepted"
}
```

**语义**:
- run 不存在：`404`
- run 已终态（`succeeded/failed/canceled`）：`200`，`accepted=false`（幂等）
- run 活跃态（`queued/running/waiting_user`）：`200`，`accepted=true`
- 取消成功后：
  - `status = canceled`
  - `error.code = CANCELED_BY_USER`
  - SSE 会推送 `status=canceled` 与 `end(reason=terminal)`

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

## 5. Web 管理界面 (UI)

### 打开管理界面
`GET /ui`

返回技能管理页面。页面提供：
- 已安装 Skill 列表（含用途描述）
- Skill 包上传与安装入口
- 安装状态轮询与结果回显
- Skill/Engine/Run 页面主数据源统一迁移到 management API 语义。

### 局部刷新技能列表（Management Adapter）
`GET /ui/management/skills/table`

用于页面局部刷新。可选参数：
- `highlight_skill_id`：高亮显示某个 skill 行（安装成功后使用）

兼容旧接口（已弃用）：
- `GET /ui/skills/table`

### 内建 E2E 示例客户端服务（独立端口）

内建 E2E 示例客户端是独立 FastAPI 服务（默认端口 `8011`），用于模拟真实前端调用链路，不复用 `/ui/*` 路由。

配置：
- `SKILL_RUNNER_E2E_CLIENT_PORT`：客户端端口，默认 `8011`；无效值回退到 `8011`。
- `SKILL_RUNNER_E2E_CLIENT_BACKEND_BASE_URL`：后端 API 地址，默认 `http://127.0.0.1:8000`。
- `SKILL_RUNNER_E2E_CLIENT_RECORDINGS_DIR`：录制回放文件目录，默认 `e2e_client/recordings`。

主要页面与接口：
- `GET /`：读取并展示 Skill 列表。
- `GET /skills/{skill_id}/run`：按 schema 渲染输入页（engine/execution_mode/model + inline/parameter/file + runtime_options）。
- `POST /skills/{skill_id}/run`：提交执行（创建 run + 可选上传 zip）。
- `GET /runs/{request_id}`：运行观测页（stdout 主对话区、stderr 独立窗口、pending/reply 交互）。
- `GET /runs/{request_id}/result`：结果与产物展示页。
- `GET /recordings`：录制会话列表。
- `GET /recordings/{request_id}`：单步回放页。
- `GET /api/runs/{request_id}/events`：代理后端 management SSE。
- `POST /api/runs/{request_id}/reply`：代理后端 reply 并写入录制。
- `GET /api/recordings/{request_id}`：读取录制 JSON。

### 页面上传安装 Skill 包
`POST /ui/skill-packages/install`

与 `POST /v1/skill-packages/install` 使用同一套后端安装逻辑，返回 HTML 片段用于前端状态轮询。

### 页面查询安装状态
`GET /ui/skill-packages/{request_id}/status`

返回 HTML 片段（含当前状态与错误信息）。终态成功后会自动触发技能列表刷新并高亮新安装 skill。

### 浏览单个 Skill 包结构（只读）
`GET /ui/skills/{skill_id}`

返回该 skill 的详情页面，包含：
- 基本信息（id/name/description/version/engines）
- 包结构树（目录与文件）
- 文件预览区域（只读）

### 预览 Skill 文件（只读）
`GET /ui/skills/{skill_id}/view?path=<relative_path>`

返回文件预览 HTML 片段。

约束与行为：
- `path` 必须是 skill 根目录内的相对路径。
- 拒绝绝对路径、`..` 路径穿越和目录逃逸。
- 文本文件可预览；二进制文件显示“不可预览（无信息）”。
- 文本文件预览大小上限为 `256KB`，超限显示“文件过大不可预览”。

### Engine 管理页面
`GET /ui/engines`

页面能力：
- 查看 Engine 状态与检测到的 CLI 版本；
- 触发“升级全部”与“按引擎升级”；
- 跳转到 Engine 模型管理页。
- 在页面下方内嵌 TUI 终端（ttyd 网关）。
- 每个引擎提供“在内嵌终端中启动 TUI”按钮（同一时刻仅允许一个活跃会话）。
- 启动返回包含 `sandbox_status`/`sandbox_message`（观测信息，默认不阻断启动）。
- Gemini 内嵌 TUI 在容器沙箱运行时可用时会显式追加 `--sandbox`（不可用时降级启动并保留状态提示）。
- iFlow 内嵌 TUI 当前固定非沙箱运行，并返回告警状态（其沙箱依赖 Docker 镜像执行，不符合当前内嵌 TUI 设计）。
- 内嵌 TUI 路径默认禁用三引擎 shell 工具能力（最小权限策略）。
- 内嵌 TUI 安全配置与 RUN 路径（`/v1/jobs`）配置隔离，不复用 RUN 的权限融合策略。

终端相关接口（JSON）：
- `GET /ui/engines/tui/session`
- `POST /ui/engines/tui/session/start`（`engine`，返回会话与 sandbox 探测状态）
- `POST /ui/engines/tui/session/stop`
- `POST /ui/engines/tui/session/input`（已废弃，返回 `410`）
- `POST /ui/engines/tui/session/resize`（已废弃，返回 `410`）

运行说明：
- 终端实际由 `ttyd` 提供，前端会按会话返回的端口嵌入 `http://<host>:<ttyd_port>/`。
- 容器部署时需显式映射 ttyd 端口（默认 `7681:7681`）。

兼容性说明：
- 旧页面 `GET /ui/engines/auth-shell` 已下线，返回 `404`。

### Engine 列表数据（Management Adapter）
`GET /ui/management/engines/table`

兼容旧接口（已弃用）：
- `GET /ui/engines/table`

### Engine 升级状态轮询（HTML partial）
`GET /ui/engines/upgrades/{request_id}/status`

用于轮询展示升级任务状态，以及 per-engine 的 stdout/stderr/error。

### Engine 模型管理页面
`GET /ui/engines/{engine}/models`

页面能力：
- 查看当前 `manifest.json`、解析到的快照、模型列表；
- 通过表单新增“当前检测版本”的模型快照（add-only）。

### Run 观测页面
`GET /ui/runs`

页面能力：
- 按 `request_id` 展示 run 列表（关联 `run_id`）；
- 展示当前状态、`pending_interaction_id`、`interaction_count`、`recovery_state` 与更新时间；
- 轮询建议遵循 `poll_logs`：`queued/running=true`，`waiting_user=false`；
- 支持自动刷新列表。

### Run 列表数据（Management Adapter）
`GET /ui/management/runs/table`

兼容旧接口（已弃用）：
- `GET /ui/runs/table`

### Run 详情页面（对话窗口）
`GET /ui/runs/{request_id}`

页面能力：
- 展示 request/run 基本信息；
- 展示 run 文件树（只读）与文件预览；文件区采用最大高度约束并在区内滚动；
- 通过 SSE 实时查看输出：stdout 作为主对话区，stderr 在独立窗口展示；
- `waiting_user` 下展示 pending 并提交 reply；
- 支持 cancel 动作并收敛到终态。
- 外部前端与内建 UI 均应遵循同一管理契约（`/v1/management/*`），避免分叉语义。

### 预览 Run 文件（Management Adapter）
`GET /ui/management/runs/{request_id}/view?path=<relative_path>`

行为与约束与 Skill 预览一致：
- 禁止绝对路径、`..` 路径穿越与目录逃逸；
- 文本可预览；二进制显示不可预览；超大文件不预览。

兼容旧接口（已弃用）：
- `GET /ui/runs/{request_id}/view?path=<relative_path>`

### Run 日志 tail（HTML partial，已弃用）
`GET /ui/runs/{request_id}/logs/tail`

返回 stdout/stderr 的 tail 内容（默认尾部窗口），当 run 状态为 `queued/running` 时前端会自动轮询刷新。

替代路径：
- `GET /v1/management/runs/{request_id}/events`

### UI 基础鉴权

可通过环境变量启用 Basic Auth：
- `UI_BASIC_AUTH_ENABLED=true|false`（默认 `false`）
- `UI_BASIC_AUTH_USERNAME`
- `UI_BASIC_AUTH_PASSWORD`

行为：
- 开启后，`/ui/*`、`/v1/skill-packages/*`、`/v1/engines/upgrades*`、`/v1/engines/{engine}/models/manifest`、`/v1/engines/{engine}/models/snapshots` 需要 Basic Auth；
- 若开启但用户名或密码缺失，服务启动失败（fail fast）。

### 本地鉴权启动脚本

项目提供 `scripts/start_ui_auth_server.sh`，用于注入 UI 鉴权环境变量并启动服务（默认开启 Basic Auth）。

示例：
```bash
./scripts/start_ui_auth_server.sh
```

### 旧 UI 数据接口弃用与移除窗口

- 当前默认策略：`warn`（返回旧行为 + 响应头 `Deprecation/Sunset/Link`）。
- 可切换移除策略：`SKILL_RUNNER_UI_LEGACY_API_MODE=gone`（返回 `410 Gone`）。
- Sunset 默认日期：`2026-06-30`（可通过 `SKILL_RUNNER_UI_LEGACY_API_SUNSET` 调整）。

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
- `GET /v1/temp-skill-runs/{request_id}/events`
- `POST /v1/temp-skill-runs/{request_id}/cancel`

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
- 元数据约束：`runner.json.engines` 可选、`runner.json.unsupport_engine` 可选；若同时声明则不允许重复且计算后的有效引擎集合必须非空。`runner.json.artifacts` 可选（若提供需为数组）。
- 包大小限制：受 `TEMP_SKILL_PACKAGE_MAX_BYTES` 控制（默认 20MB）。

### 生命周期与清理
- 临时 skill 包与解压目录默认在终态（`succeeded`/`failed`/`canceled`）后立即清理。
- `runtime_options.debug_keep_temp=true` 时，跳过立即清理，仅保留用于调试。
- 若立即清理失败，仅记录 warning，不影响终态；由后台定时清理兜底。

---

## 4. 引擎 (Engines)

说明：
- `/v1/engines*` 保留执行域/运维能力与兼容语义。
- 管理页展示建议优先使用 `/v1/management/engines*`（字段稳定、前端友好）。

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

### 获取引擎鉴权与路径状态（受 Basic Auth 保护）
`GET /v1/engines/auth-status`

说明：
- 用于诊断服务当前实际使用的 CLI 路径来源（managed/global）及鉴权文件就绪情况。
- 该接口返回静态就绪判断（不触发真实模型调用，不消耗 token）。

**Response** (`EngineAuthStatusResponse`):
```json
{
  "engines": {
    "iflow": {
      "managed_present": true,
      "managed_cli_path": "/home/foo/.local/share/skill-runner/agent-cache/npm/bin/iflow",
      "global_available": true,
      "global_cli_path": "/usr/local/bin/iflow",
      "effective_cli_path": "/home/foo/.local/share/skill-runner/agent-cache/npm/bin/iflow",
      "effective_path_source": "managed",
      "credential_files": {
        "iflow_accounts.json": true,
        "oauth_creds.json": false
      },
      "auth_ready": false
    }
  }
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

### 获取引擎模型 Manifest 视图（受 Basic Auth 保护）
`GET /v1/engines/{engine}/models/manifest`

**Response** (`EngineManifestViewResponse`):
```json
{
  "engine": "codex",
  "cli_version_detected": "0.89.0",
  "manifest": {
    "engine": "codex",
    "snapshots": [{"version": "0.89.0", "file": "models_0.89.0.json"}]
  },
  "resolved_snapshot_version": "0.89.0",
  "resolved_snapshot_file": "models_0.89.0.json",
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

### 新增当前版本模型快照（受 Basic Auth 保护）
`POST /v1/engines/{engine}/models/snapshots`

**Request** (`EngineSnapshotCreateRequest`):
```json
{
  "models": [
    {
      "id": "gpt-5.3-codex",
      "display_name": "GPT-5.3 Codex",
      "deprecated": false,
      "notes": "manual snapshot",
      "supported_effort": ["low", "medium", "high", "xhigh"]
    }
  ]
}
```

约束：
- 版本号固定使用服务端当前检测到的 `cli_version_detected`；
- 若目标 `models_<version>.json` 已存在，则拒绝（不覆盖）；
- 成功后立即刷新内存模型注册表。

### 创建引擎升级任务（受 Basic Auth 保护）
`POST /v1/engines/upgrades`

**Request** (`EngineUpgradeCreateRequest`):
```json
{
  "mode": "single",
  "engine": "gemini"
}
```

说明：`mode=all` 时必须省略 `engine` 字段。

**Response** (`EngineUpgradeCreateResponse`):
```json
{
  "request_id": "ef5e7ff9-1f6a-4a4f-a317-b8daaa13f2cf",
  "status": "queued"
}
```

### 查询引擎升级任务状态（受 Basic Auth 保护）
`GET /v1/engines/upgrades/{request_id}`

**Response** (`EngineUpgradeStatusResponse`):
```json
{
  "request_id": "ef5e7ff9-1f6a-4a4f-a317-b8daaa13f2cf",
  "mode": "all",
  "requested_engine": null,
  "status": "failed",
  "results": {
    "codex": {"status": "succeeded", "stdout": "...", "stderr": "", "error": null},
    "gemini": {"status": "failed", "stdout": "...", "stderr": "...", "error": "Upgrade command exited with code 1"},
    "iflow": {"status": "succeeded", "stdout": "...", "stderr": "", "error": null}
  },
  "created_at": "2026-02-12T10:00:00.000000",
  "updated_at": "2026-02-12T10:00:12.000000"
}
```
