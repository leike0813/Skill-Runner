# API 接口文档 (API Reference)

本文档描述 Skill Runner 提供的 RESTful API 接口。

说明（内部实现）：当前 adapter 已收敛为 execution adapter + 组件模型，属于内部重构，
不影响本文档中的对外 API 契约。

## Base URL
默认为 `http://localhost:9813` (取决于部署配置)。
建议使用版本化前缀：`/v1`。

示例：
`http://localhost:9813/v1`

---

## 可达性探测（Reachability Probe）

- `GET /v1/system/ping`：极轻量可达性探测（无响应体）
- `HEAD /v1/system/ping`：极轻量可达性探测（无响应体）

`GET /v1/system/ping`

**Response**:
- `204 No Content`
- 响应体为空
- 不依赖数据库、技能扫描或引擎状态探测，适合作为 liveness/readiness 的快速探测入口

---

## 0. 管理 API（Management，推荐）
<a id="management-api-recommended"></a>

`/v1/management/*` 提供前端无关的统一管理契约，适用于内置 UI 与外部前端（如插件 WebView）复用。

### System 管理
- `GET /v1/management/system/settings`：获取系统设置（日志配置、鉴权会话日志持久化开关、数据重置确认文本）
- `PUT /v1/management/system/settings`：更新系统设置（当前支持日志级别配置）
- `GET /v1/management/system/logs/query`：查询系统日志与 bootstrap 日志（关键词/级别/时间范围/分页）
- `POST /v1/management/system/reset-data`：执行数据重置（**破坏性操作**，需确认文本）

### Skill 管理
- `GET /v1/management/skills`：技能摘要列表（`id/name/version/engines/unsupported_engines/effective_engines/is_builtin/health`）
- `GET /v1/management/skills/{skill_id}`：技能详情（额外包含 `schemas/entrypoints/files/execution_modes`）
- `GET /v1/management/skills/{skill_id}/schemas`：返回 `input/parameter/output` schema 内容（用于动态表单构建）

### Engine 管理
- `GET /v1/management/engines`：引擎摘要列表（`engine/cli_version/models_count`，版本来自后台缓存）
- `GET /v1/management/engines/{engine}`：引擎详情（额外包含 `models/upgrade_status/last_error`；模型项在适用时可带 `provider/provider_id/model/source`）
- `GET /v1/management/engines/{engine}/auth/import/spec`：返回该引擎（及 provider-aware provider）导入鉴权文件要求
- `POST /v1/management/engines/{engine}/auth/import`：提交并导入鉴权文件（multipart）

### Run 管理（对话窗口）
- `GET /v1/management/runs`：运行摘要列表（支持 `page/page_size`，兼容 `limit`）
- `GET /v1/management/runs/{request_id}`：会话状态（含 `pending_interaction_id`、`interaction_count`、`recovery_state/recovered_at/recovery_reason`）
- `GET /v1/management/runs/{request_id}/files`：文件树
- `GET /v1/management/runs/{request_id}/file?path=...`：文件预览
- `GET /v1/management/runs/{request_id}/events`：SSE 实时输出（复用 jobs 事件语义）
- `GET /v1/management/runs/{request_id}/events/history`：结构化历史事件（支持 `from_seq/to_seq/from_ts/to_ts`）
- `GET /v1/management/runs/{request_id}/chat`：SSE 对话事件流（复用 jobs chat 语义）
- `GET /v1/management/runs/{request_id}/chat/history`：结构化对话历史（支持 `from_seq/to_seq/from_ts/to_ts`）
- `GET /v1/management/runs/{request_id}/protocol/history`：协议级事件历史（FCMP/RASP/Orchestrator，支持 `attempt` 与 `limit`）
- `POST /v1/management/runs/{request_id}/protocol/rebuild`：手动重构该 run 的协议审计文件（全 attempts，覆盖写回并自动备份）
- `GET /v1/management/runs/{request_id}/timeline/history`：Run 级时序历史（五泳道聚合，支持 `cursor/limit`）
- `GET /v1/management/runs/{request_id}/logs/range`：按字节区间读取 `stdout/stderr/pty` 片段（供 `raw_ref` 回跳，支持 `attempt`）
- `GET /v1/management/runs/{request_id}/pending`：查询待决交互
- `POST /v1/management/runs/{request_id}/reply`：提交交互回复
- `POST /v1/management/runs/{request_id}/cancel`：取消运行

### Local Runtime 租约（本地模式）
- `GET /v1/local-runtime/status`：读取本地租约管理状态（是否启用、TTL、活跃租约数）
- `POST /v1/local-runtime/lease/acquire`：申请租约（返回 `lease_id`、`expires_at`）
- `POST /v1/local-runtime/lease/heartbeat`：续租
- `POST /v1/local-runtime/lease/release`：释放租约

说明：
- 管理 API 是推荐的前端消费面。
- 现有 `/v1/skills*`、`/v1/engines*`、`/v1/jobs*`、`/v1/temp-skill-runs*` 保持兼容，用于执行链路与存量调用。
- `local-runtime` 接口仅在 `SKILL_RUNNER_RUNTIME_MODE=local` 下可用；非 local 模式返回 `409`。

### 本地运行租约接口
`GET /v1/local-runtime/status`

**Response** (`LocalRuntimeStatusResponse`):
```json
{
  "enabled": true,
  "ttl_seconds": 60,
  "heartbeat_interval_seconds": 20,
  "active_leases": 1,
  "has_ever_had_lease": true
}
```

`POST /v1/local-runtime/lease/acquire`

**Request Body** (`LocalLeaseAcquireRequest`):
```json
{
  "owner_id": "zotero-plugin",
  "metadata": {
    "client": "zotero"
  }
}
```

**Response** (`LocalLeaseAcquireResponse`):
```json
{
  "lease_id": "f85e88f5-bf4e-4fd5-b66e-f490d4f156f2",
  "ttl_seconds": 60,
  "heartbeat_interval_seconds": 20,
  "expires_at": "2026-03-12T12:01:00Z",
  "active_leases": 1
}
```

`POST /v1/local-runtime/lease/heartbeat`

**Request Body**:
```json
{
  "lease_id": "f85e88f5-bf4e-4fd5-b66e-f490d4f156f2"
}
```

`POST /v1/local-runtime/lease/release`

**Request Body**:
```json
{
  "lease_id": "f85e88f5-bf4e-4fd5-b66e-f490d4f156f2"
}
```

### 获取系统设置
`GET /v1/management/system/settings`

**Response** (`ManagementSystemSettingsResponse`):
```json
{
  "logging": {
    "server_level": "INFO",
    "runtime_level": "DEBUG"
  },
  "engine_auth_session_log_persistence_enabled": true,
  "reset_confirmation_text": "CONFIRM RESET"
}
```

### 更新系统设置
`PUT /v1/management/system/settings`

**Request Body** (`ManagementSystemSettingsUpdateRequest`):
```json
{
  "logging": {
    "server_level": "WARNING",
    "runtime_level": "INFO"
  }
}
```

**Response**: 同 `GET /v1/management/system/settings` 返回最新生效状态。

**错误码**:
- `400`: 日志级别验证失败（如非法级别名）。
- `500`: 文件系统写入错误。

### 查询系统日志（System Console）
`GET /v1/management/system/logs/query`

用于管理端 **System Console** 查询日志。支持 `system`（`skill_runner.log*`）与 `bootstrap`（`bootstrap.log*`）两种日志源。

**Query 参数**:
- `source`（必填）：`system` / `bootstrap`
- `cursor`（可选，默认 `0`）：分页偏移
- `limit`（可选，默认 `200`，最大 `1000`）
- `q`（可选）：关键词（对 `message/raw` 做 case-insensitive 匹配）
- `level`（可选）：`DEBUG|INFO|WARNING|ERROR|CRITICAL`
- `from_ts` / `to_ts`（可选）：ISO8601 时间范围过滤

**Response** (`ManagementSystemLogQueryResponse`):
```json
{
  "source": "system",
  "items": [
    {
      "ts": "2026-03-07T01:20:52Z",
      "level": "ERROR",
      "message": "Failed to install codex",
      "raw": "2026-03-07 01:20:52 ERROR server.test: Failed to install codex",
      "source": "system",
      "file": "skill_runner.log",
      "line_no": 120
    }
  ],
  "next_cursor": 1,
  "total_matched": 42
}
```

**错误码**:
- `400`: `source` 或 `level` 参数非法。
- `500`: 日志文件读取失败（文件系统错误）。

**过滤规则**:
- 仅允许白名单日志族：
  - `source=system` → `skill_runner.log*`
  - `source=bootstrap` → `bootstrap.log*`
- 不支持任意路径输入。
- 时间过滤为 best-effort；无法解析时间戳的行在启用时间过滤时会被排除。

### 数据重置
`POST /v1/management/system/reset-data`

**⚠️ 破坏性操作** — 将删除运行记录、缓存条目及可选的日志/引擎目录/Agent 状态缓存数据。

**Request Body** (`ManagementDataResetRequest`):
```json
{
  "confirmation": "CONFIRM RESET",
  "include_logs": true,
  "include_engine_catalog": false,
  "include_engine_auth_sessions": false,
  "dry_run": true
}
```

**说明**:
- `confirmation` 必须精确等于 `GET /v1/management/system/settings` 返回的 `reset_confirmation_text`。
- `dry_run=true` 时仅返回将被删除的统计，不执行实际删除。
- `include_engine_auth_sessions` 仅在系统已启用 `ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED` 时生效。

**Response** (`ManagementDataResetResponse`):
```json
{
  "dry_run": true,
  "runs_deleted": 42,
  "requests_deleted": 42,
  "cache_entries_deleted": 15,
  "log_dirs_deleted": 42,
  "engine_catalog_reset": false,
  "agent_status_reset": false,
  "engine_auth_sessions_deleted": 0
}
```

**错误码**:
- `400`: `confirmation` 文本不匹配。
- `409`: 另一个重置操作正在进行中。
- `500`: 文件系统错误。

### 管理 Run 摘要列表（分页）
`GET /v1/management/runs`

返回管理端 Run 摘要列表，支持分页。

**Query 参数**:
- `page`（可选，默认 `1`，最小 `1`）
- `page_size`（可选，默认 `20`，最小 `1`，最大 `200`）
- `limit`（可选，兼容旧参数；未提供 `page_size` 时生效）

**Response** (`ManagementRunListResponse`):
```json
{
  "runs": [
    {
      "request_id": "d290f1ee-...",
      "run_id": "9d2c1f31-...",
      "skill_id": "demo-interactive-skill",
      "engine": "codex",
      "model": "gpt-5.4",
      "status": "running",
      "pending_interaction_id": null,
      "interaction_count": 0,
      "updated_at": "2026-03-11T09:20:00Z"
    }
  ],
  "total": 128,
  "page": 1,
  "page_size": 20,
  "total_pages": 7
}
```

### 对话事件流（Chat SSE）
`GET /v1/management/runs/{request_id}/chat`

返回 `text/event-stream`，用于实时消费 FCMP 对话事件（与 `events` 流语义一致，但面向对话窗口场景）。

**Query 参数**:
- `cursor`（可选，默认 `0`）：续传游标。

**关联接口**: 该接口在 `/v1/jobs/{request_id}/chat` 和 `/v1/temp-skill-runs/{request_id}/chat` 同样可用，语义一致。

### 结构化对话历史
`GET /v1/management/runs/{request_id}/chat/history`

按区间拉取对话历史（结构与 `events/history` 一致）。

**Query 参数**:
- `from_seq` / `to_seq`（可选）：按序号区间拉取
- `from_ts` / `to_ts`（可选）：按时间区间拉取（ISO8601）

**关联接口**: 该接口在 `/v1/jobs/{request_id}/chat/history` 和 `/v1/temp-skill-runs/{request_id}/chat/history` 同样可用。

**事件 kind 说明（增量）**:
- `assistant_process`：assistant 过程消息（由 FCMP 的 `assistant.reasoning` / `assistant.tool_call` / `assistant.command_execution` 派生）
- `assistant_final`：assistant 最终答复
- `interaction_reply`：用户交互回复
- `auth_submission`：用户鉴权输入
- `orchestration_notice`：系统编排提示

说明：
- `assistant.message.promoted` 不会单独派生 chat 正文事件，仅作为收敛边界语义。
- `assistant_process` 事件可在 `correlation` 中包含 `process_type`、`message_id`、`fcmp_seq`、`summary`、`details`。

### 协议级事件历史
`GET /v1/management/runs/{request_id}/protocol/history`

返回指定协议流的原始事件序列，用于运行调试与协议复盘。

**Query 参数**:
- `stream`（必填）：`fcmp` / `rasp` / `orchestrator`
- `from_seq` / `to_seq`（可选）：按序号区间拉取
- `from_ts` / `to_ts`（可选）：按时间区间拉取（ISO8601）
- `attempt`（可选，`>=1`）：指定恢复尝试轮次
- `limit`（可选，默认 `200`，最大 `1000`）：返回窗口上限

**Response**:
```json
{
  "request_id": "d290f1ee-...",
  "stream": "fcmp",
  "attempt": 1,
  "available_attempts": [1, 2],
  "count": 25,
  "events": [...]
}
```

**错误码**:
- `400`: `stream` 值非法。
- `404`: `request_id` 或 run 不存在。

说明：
- 该接口仅在管理 API 提供（`/v1/jobs` 和 `/v1/temp-skill-runs` 不提供此接口）。
- FCMP 过程事件已扩展为通用类型：`assistant.reasoning` / `assistant.tool_call` / `assistant.command_execution` / `assistant.message.promoted`（保留 `assistant.message.final`）。
- RASP 过程事件对应为 `agent.reasoning` / `agent.tool_call` / `agent.command_execution` / `agent.message.promoted`（保留 `agent.message.final`）。
- RASP 额外包含回合标记：`agent.turn_start` / `agent.turn_complete`（仅审计，不映射 FCMP）。
- `agent.turn_complete.data` 可直接包含结构化统计信息（例如 Gemini `stats`、Codex `usage`、OpenCode `cost/tokens`、iFlow execution metrics）。
- RASP 生命周期扩展事件：`lifecycle.run_handle`（`data.handle_id`，仅审计，不映射 FCMP/chat）。
- FCMP 不允许 `assistant.turn_*` 事件类型。
- 同一 `message_id` 的收敛顺序为 `*.message.promoted` 先于 `*.message.final`。
- `raw.stdout/raw.stderr` 事件仍保持原类型，`data.line` 可能为多行归并文本（string，向后兼容）。
- Gemini 解析器在命中整批 JSON 时可产出 `parsed.json` 事件（RASP），用于呈现 `stream/session_id/response/summary/details` 结构化信息。
- run 进入 terminal（`succeeded/failed/canceled`）后，`stream=rasp|fcmp` 的历史查询按审计文件口径返回（不混 live journal 增量）。

### 手动重构协议审计
`POST /v1/management/runs/{request_id}/protocol/rebuild`

对指定 run 的全部 attempts 进行协议重构。  
重构模式固定为 `strict_replay`：仅按真实运行链路回放（`io_chunks + orchestrator_events + meta`），关键证据缺失时该 attempt 失败且不覆写。  
写回覆盖前会自动备份已有审计文件到 `.audit/rebuild_backups/<timestamp>/attempt-<N>/`。

**Request Body**: 无

**Response**:
```json
{
  "request_id": "d290f1ee-...",
  "run_id": "run-123",
  "mode": "strict_replay",
  "success": true,
  "backup_dir": "/.../run-123/.audit/rebuild_backups/20260310T120000000000Z",
  "attempts": [
    {
      "attempt": 1,
      "mode": "strict_replay",
      "source": "io_chunks",
      "written": true,
      "reason": "OK",
      "event_count": 58,
      "fcmp_count": 37,
      "diagnostics": [],
      "success": true
    }
  ]
}
```

**错误码**:
- `404`: `request_id` 不存在、run 不存在或 run 目录缺失。

说明：
- 此接口为人工运维动作，不会在页面访问或常规历史读取时自动触发。
- 本次重构范围是“整个 run（全部 attempts）”，不会只重构单 attempt。
- 重构不会做“运行态补偿重算注入”；仅允许真实回放链路自然产出事件。
- 每个 attempt 单独执行：失败 attempt 不覆写，成功 attempt 可独立覆写。

### Run 级时序历史
`GET /v1/management/runs/{request_id}/timeline/history`

返回跨流聚合后的 Run Scope 时间线（Orchestrator / Parser-RASP / Protocol-FCMP / Chat / Client）。

**Query 参数**:
- `cursor`（可选，默认 `0`）：按 `timeline_seq` 增量拉取游标
- `limit`（可选，默认 `100`，最大 `500`）：本次返回窗口大小

**Response**:
```json
{
  "request_id": "d290f1ee-...",
  "count": 2,
  "events": [
    {
      "timeline_seq": 101,
      "ts": "2026-03-06T10:00:01Z",
      "lane": "protocol_fcmp",
      "kind": "conversation.state.changed",
      "summary": "state: queued -> running",
      "attempt": 2,
      "source_stream": "fcmp",
      "raw_ref": {
        "attempt_number": 2,
        "stream": "stdout",
        "byte_from": 0,
        "byte_to": 64
      },
      "details": {
        "stream": "fcmp",
        "event": {}
      }
    }
  ],
  "cursor_floor": 101,
  "cursor_ceiling": 132,
  "source": "mixed"
}
```

**错误码**:
- `404`: `request_id` 或 run 不存在。

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
- schema 解析规则：
  - 优先读取 `runner.json.schemas.input/parameter/output`
  - 若声明缺失、为空、非法、越界或目标文件不存在，则回退到固定文件名：
    - `assets/input.schema.json`
    - `assets/parameter.schema.json`
    - `assets/output.schema.json`
  - 若 schema 声明失败但 fallback 存在：校验通过并记录 warning
  - 若 schema 声明失败且 fallback 也不存在：技能包校验失败
- engine config 解析规则：
  - 可选声明 `runner.json.engine_configs.{engine}`
  - 声明失败时静默回退到固定文件名：
    - `codex` -> `assets/codex_config.toml`
    - `gemini` -> `assets/gemini_settings.json`
    - `qwen` -> `assets/qwen_config.json`
    - `opencode` -> `assets/opencode_config.json`
  - 若声明和 fallback 都不存在：视为“未提供 skill-specific engine config”，不阻断运行
- `input/parameter/output` schema 会在上传阶段执行服务端 meta-schema 预检：
  - `input.schema.json` 的 `x-input-source` 仅允许 `file` / `inline`；
  - `output.schema.json` 的 `x-type` 仅允许 `artifact` / `file`；
  - 三个 schema 需满足对象型 JSON Schema 基本结构约束。
- `SKILL.md` frontmatter 的 `name`、`assets/runner.json` 的 `id`、顶层目录名必须完全一致。
- `runner.json.engines` 为可选字段；缺失时默认按系统支持的全部引擎处理。
- `runner.json.unsupported_engines` 为可选字段；用于声明显式不支持引擎。
- 若 `engines` 与 `unsupported_engines` 同时存在，二者不允许重复；计算后的有效引擎集合必须非空。
- `runner.json` 必须包含非空 `execution_modes` 列表，且值仅允许 `auto` / `interactive`。
- `runner.json.max_attempt` 为可选正整数（`>=1`），仅在 `interactive` 模式生效：
  - 目标合同下，只有显式最终分支（`__SKILL_DONE__ = true`）才算完成。
  - 当 `attempt_number >= max_attempt` 且当轮既未产出合法最终分支，也未进入合法 pending 分支时，run 失败并返回 `INTERACTIVE_MAX_ATTEMPT_EXCEEDED`。
- `runner.json` 的 `artifacts` 可选；若提供，必须为数组。  
  若未提供，服务端会基于 `output.schema.json` 中的 artifact 声明推导运行时产物合同。
- `runner.json.runtime.default_options` 可选；用于声明 skill 默认 runtime options：
  - 仅 runtime option 白名单键参与合成；
  - 请求体 `runtime_options` 同名键优先覆盖；
  - 非法默认值会被忽略并记录 warning（不阻断执行）。
- `runner.json` 必须包含可解析的 `version`。

**更新规则**:
- 持久注册表采用双目录：`skills_builtin/`（内建）与 `skills/`（用户）；同 `skill_id` 时用户目录优先。
- 若 `skill_id` 已存在，则只允许严格升版（`new_version > installed_version`）。
- 不允许降级或同版本覆盖。
- 更新时旧版本会归档到用户目录 `skills/.archive/{skill_id}/{old_version}/`。
- 若目标归档路径已存在，则更新失败并保持现有技能不变。
- 若用户目录已存在但不是有效已安装结构（例如缺失 `assets/runner.json`），会被视为“无已安装版本”，并先移动到 `skills/.invalid/` 后按全新安装处理。
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
  "engine": "qwen",            // 可选: "gemini" / "codex" / "opencode" / "claude" / "qwen" (默认: codex)
  "provider_id": "qwen-oauth",
  "effort": "default",
  "input": {
    "query": "some inline input payload"
  },
  "parameter": {
    "divisor": 1                 // 仅包含配置参数
  },
  "model": "coder-model",
  "runtime_options": {}
}
```

**关键说明**:
- **输入分离（Mixed Input）**:
  - 顶层 `input` 用于传递业务输入（可为 string/array/object）。
  - 对 `input.schema.json` 中 `x-input-source=inline` 的字段，值直接来自请求体 `input`。
  - 对 `x-input-source=file`（或未声明，默认 file）的字段，值也在请求体 `input` 中显式提交，但值必须是 `uploads/` 根下相对路径（例如 `papers/a.pdf`）。
- **参数分离**: API 请求体中的 `parameter` 字段仅用于传递 `parameter.schema.json` 中定义的数值或配置。
- **模型字段**:
  - 新标准写法为 `provider_id + model + effort`。
  - `model` 为顶层字段，先通过 `GET /v1/engines/{engine}/models` 获取可用模型列表。
  - `effort` 为空时按 `"default"` 处理。
  - 对支持 effort 的模型，`"default"` 会映射到引擎实际生效值；通常为 `"medium"`。
  - 对不支持 effort 的模型，`supported_effort` 固定为 `["default"]`；此时传入任何 `effort` 都不会改变行为。
  - 单 provider 引擎（`codex`、`gemini`）允许 `provider_id` 为空或任意值；系统会统一收口到 canonical provider。
  - 多 provider 引擎（`claude`、`qwen`、`opencode`）标准写法必须显式带 `provider_id`。
  - 旧客户端仍兼容：
    - `model="provider/model@effort"`
    - `model="provider/model"`
    - `model="model@effort"`
  - 兼容仅存在于请求解析层；新客户端不应再主动拼接这些旧式字符串。
  - `qwen` 的 skill/runtime 配置统一写入 `.qwen/settings.json`，由 `default -> runtime -> enforced` 合成。
- **运行时选项**:
  - `runtime_options.execution_mode` 支持 `auto`（默认）与 `interactive`。
  - 会话回复超时键：`runtime_options.interactive_reply_timeout_sec`（默认 `1200`）。
  - `runtime_options.hard_timeout_seconds` 支持正整数，覆盖本次 run 的引擎硬超时。
  - `interactive` 下可设置 `runtime_options.interactive_auto_reply`：
    - `false`（默认）：严格等待用户回复，超时不自动继续。
    - `true`：等待超时后自动决策并继续执行。
  - skill 若声明 `runner.json.runtime.default_options`，系统会先应用该默认值，再应用请求值覆盖。
  - 非法 skill 默认 runtime options 会被忽略，并记录 lifecycle warning/diagnostic。
  - `interactive` 模式始终采用单一可恢复会话语义，内部保存会话句柄；对外不暴露 `interactive_profile.kind`。
  - 引擎执行启用硬超时，默认 `1200s`（环境变量 `SKILL_RUNNER_ENGINE_HARD_TIMEOUT_SECONDS` 可覆盖）。
  - 超时后会终止子进程并将 run 置为 `failed`（错误码 `TIMEOUT`）。
- **缓存策略**:
  - 设置 `runtime_options.no_cache=true` 将跳过缓存命中检查。
  - `runtime_options.execution_mode=interactive` 时，系统会跳过缓存命中，且不会写入 `cache_entries`。
- **Debug Bundle**: 普通 bundle 与 Debug Bundle 是两个独立下载产物；是否下载 debug 版本不再由 `runtime_options` 控制。
- **临时 Skill 调试保留**: `runtime_options.debug_keep_temp=true` 仅用于 `/v1/temp-skill-runs`，表示终态后不立即删除临时 skill 包与解压目录。
- **模型校验**: `model` 必须在 `GET /v1/engines/{engine}/models` 的 allowlist 中。
- **引擎约束**: `engine` 必须包含在 skill 的有效引擎集合中（`effective_engines = (engines 或 全量支持引擎) - unsupported_engines`），否则返回 400（`SKILL_ENGINE_UNSUPPORTED`）。
- **模式准入约束**: 请求的 `runtime_options.execution_mode` 必须包含在 skill 的 `execution_modes` 声明中，否则返回 400（`SKILL_EXECUTION_MODE_UNSUPPORTED`）。
- **文件输入**:
  - file 类型输入的路径声明也通过请求体 `input` 提交；
  - `/upload` 仅负责上传 zip 并解压到 `uploads/`；
  - 旧的 `uploads/<input_key>` 严格键匹配仅作为兼容回退，不再是主协议。
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
  "model": "gemini-3.1-pro-preview",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:01:00Z",
  "pending_interaction_id": 12,
  "pending_auth_session_id": null,
  "pending_payload": null,
  "interaction_count": 3,
  "recovery_state": "recovered_waiting",
  "recovered_at": "2026-02-16T00:05:00Z",
  "recovery_reason": "resumable_waiting_preserved",
  "auto_decision_count": 0,
  "last_auto_decision_at": null,
  "requested_execution_mode": "interactive",
  "effective_execution_mode": "interactive",
  "conversation_mode": "single_turn",
  "interactive_auto_reply": false,
  "interactive_reply_timeout_sec": 1200,
  "effective_interactive_require_user_reply": true,
  "effective_interactive_reply_timeout_sec": 1200,
  "current_attempt": 1,
  "pending_owner": null,
  "dispatch_phase": "claimed",
  "dispatch_ticket_id": null,
  "worker_claim_id": null,
  "resume_ticket_id": null,
  "resume_cause": null,
  "source_attempt": null,
  "target_attempt": null,
  "warnings": [],
  "error": null
}
```

说明：
- `waiting_user` 为非终态，客户端应按 pending/reply 流程推进，而不是直接结束。
- `pending_interaction_id` 为空表示当前没有待决交互。
- `model` 为本次 run 记录的模型标识（若请求未显式指定则可能为空）。
- `pending_auth_session_id` 非空时，表示 run 正在等待引擎鉴权，客户端应查询 `auth/session`。
- `pending_payload` 包含待决事项的额外结构化载荷（如鉴权 URL 等），可用于前端直接渲染。
- 当 run 处于 `waiting_auth` 时，前端通常应同时读取 `GET /v1/jobs/{request_id}/interaction/pending` 与 `GET /v1/jobs/{request_id}/auth/session`：
  - `interaction/pending` 提供聊天侧 challenge 语义，如 `accepts_chat_input`、`input_kind`、`auth_url`、`user_code`
  - `auth/session` 提供底层引擎鉴权会话状态真相
- 若 `pending_auth.accepts_chat_input=false` 且 `pending_auth.input_kind=null`，前端应隐藏输入框并继续轮询状态；这类 challenge 仍可能返回 `auth_url` / `user_code` 供用户在浏览器中完成授权。
- `interaction_count` 为当前 request 已记录的交互轮次计数。
- `recovery_state` 取值：`none | recovered_waiting | failed_reconciled`。
- `failed_reconciled` 常见错误码：`SESSION_RESUME_FAILED`、`ORCHESTRATOR_RESTART_INTERRUPTED`。
- `requested_execution_mode`：请求时指定的执行模式。
- `effective_execution_mode`：实际生效的执行模式。
- `conversation_mode`：对话模式（`single_turn` / `multi_turn`）。
- `interactive_auto_reply`：是否启用超时自动回复。
- `interactive_reply_timeout_sec` / `effective_interactive_reply_timeout_sec`：回复超时设定/实际生效值。
- `effective_interactive_require_user_reply`：是否强制要求用户回复。
- `current_attempt`：当前执行尝试轮次。
- `pending_owner`：交互待决的归属方标识。
- `dispatch_phase`：调度阶段（`queued | dispatching | claimed | running`）。
- `dispatch_ticket_id` / `worker_claim_id`：调度令牌/Worker 认领标识，用于调试与追踪。
- `resume_ticket_id` / `resume_cause`：恢复令牌/恢复原因，可用于故障排查。
- `source_attempt` / `target_attempt`：恢复调度时的源/目标尝试轮次。
- interactive 目标输出合同说明：
  - `interactive` 采用单一 union contract。
  - 最终分支：JSON 对象，且显式 `__SKILL_DONE__ = true`；业务字段满足 `output.schema.json`。
  - 中间分支：JSON 对象，且显式 `__SKILL_DONE__ = false`，并包含非空 `message` 与对象型 `ui_hints`。
  - interactive 生命周期优先级固定为：final branch -> pending branch -> soft completion -> default waiting fallback。
  - `waiting_user` 的正式富数据来源是合法 pending JSON 分支投影，而不是独立 YAML 协议。
  - `tool_use`/tool 回显中的 marker 文本不参与完成判定。
  - 当前实现中 soft completion 与 legacy waiting fallback 仍作为 compatibility path 保留；legacy fallback 只会生成默认 pending payload，不再从 `<ASK_USER_YAML>` 或 direct ask-user object 提取富字段。

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
对外 `PendingInteraction` 形状当前保持不变；目标方向是将其稳定投影自合法 pending JSON 分支。
若某回合未命中合法 pending/final branch 且 soft completion 也不成立，系统仍可能进入 `waiting_user`，但 payload 只会是默认 fallback 版本。

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
- `status` 固定回到 `queued`，随后由调度器恢复执行下一回合。
- 当 `mode=auth` 时，`submission.kind` 除 `callback_url` / `auth_code_or_url` / `api_key` 外，也支持 `custom_provider`，用于 Claude 第三方 provider 的会话内配置提交。

**错误语义**:
- `400`: 当前请求不是 interactive 模式（`runtime_options.execution_mode != interactive`）。
- `404`: `request_id` 或 `run` 不存在。
- `409`: 非 `waiting_user` 状态提交、`interaction_id` 过期/不匹配、或 `idempotency_key` 冲突。
- `SESSION_RESUME_FAILED`: `resumable` 路径下无法提取/使用会话句柄（Codex `thread_id`、Gemini `session_id`、iFlow `session-id`）。

### 会话中导入鉴权文件 (Auth Import In Conversation)
`POST /v1/jobs/{request_id}/interaction/auth/import`

用于 `waiting_auth` 阶段且可用方法包含 `import` 时提交鉴权文件。

**Request**:
- `Content-Type`: `multipart/form-data`
- `provider_id`（可选；对 provider-aware engine 建议显式传入）
- `files`（可重复）：鉴权文件

**Response** (`InteractionReplyResponse`):
```json
{
  "request_id": "d290f1ee-6c54-4b01-90e6-...",
  "status": "queued",
  "accepted": true,
  "mode": "auth"
}
```

**行为说明**:
- 导入校验通过后，服务直接走 `auth.completed` 分支，清理 pending auth 并恢复 run 调度。
- 该接口仅在 `waiting_auth` 且当前可用方法包含 `import` 时受理。

**错误码**:
- `409`: 当前不在待鉴权状态。
- `422`: 文件缺失、结构不合法、provider 不匹配或当前引擎/provider 不支持导入。

### 上传文件 (Upload File)
`POST /v1/jobs/{request_id}/upload`

为指定的 Request 上传输入文件。系统仅接受 Zip 格式的压缩包。

**Request**:
- `Content-Type`: `multipart/form-data`
- `file`: 二进制 Zip 文件。

**行为**:
- 系统会将 Zip 解压到 `data/requests/{request_id}/uploads/`。
- Zip 包内部允许任意目录结构。
- 若 create 阶段已声明 file 类型输入路径，upload 后系统会校验这些路径在 `uploads/` 下真实存在。

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
    "artifacts": ["reports/report.md"],
    "validation_warnings": [],
    "error": null
  }
}
```

**语义约束**:
- 该接口现在是 terminal-only。
- 仅当 run 已进入 `succeeded` / `failed` / `canceled` 时返回 `200`。
- 若当前仍处于 `queued` / `running` / `waiting_user` / `waiting_auth`，返回 `409`，`detail="terminal result not ready"`。
- 当前态请改读 `GET /v1/jobs/{request_id}` 与 `GET /v1/jobs/{request_id}/interaction/pending` / `GET /v1/jobs/{request_id}/auth/session`。

### 获取产物清单 (Get Artifacts)
`GET /v1/jobs/{request_id}/artifacts`

**Response** (`RunArtifactsResponse`):
```json
{
  "request_id": "d290f1ee-6c54-4b01-90e6-...",
  "artifacts": ["reports/report.md"]
}
```

### 下载 Bundle (Get Bundle)
`GET /v1/jobs/{request_id}/bundle`

**Response**:
- 直接返回 Bundle Zip 文件（`Content-Type: application/zip`）
- `Content-Disposition` 文件名为 `run_bundle.zip`

**说明**:
- 普通 bundle 采用 contract-driven 语义，仅包含 `result/result.json` 与 resolved artifact 文件，以及 `bundle/manifest.json`。

### 下载 Debug Bundle (Get Debug Bundle)
`GET /v1/jobs/{request_id}/bundle/debug`

**Response**:
- 直接返回 Debug Bundle Zip 文件（`Content-Type: application/zip`）
- `Content-Disposition` 文件名为 `run_bundle_debug.zip`

**说明**:
- Debug Bundle 会额外包含 logs 等调试文件，并使用 `bundle/manifest_debug.json`。

### 获取 Run 文件树 (Get Run Files)
`GET /v1/jobs/{request_id}/files`

返回当前 run 可浏览文件树（run scope）。

**Response** (`RunFilesResponse`):
```json
{
  "request_id": "d290f1ee-6c54-4b01-90e6-...",
  "run_id": "9d2c1f31-...",
  "entries": [
    {
      "path": "result",
      "name": "result",
      "is_dir": true,
      "depth": 0
    },
    {
      "path": "result/result.json",
      "name": "result.json",
      "is_dir": false,
      "depth": 1
    }
  ]
}
```

### 获取 Run 文件预览 (Get Run File Preview)
`GET /v1/jobs/{request_id}/file?path=...`

返回后端 canonical 文件预览载荷（与管理 UI 文件预览同源）。

**Query 参数**:
- `path`（必填）：run 目录内相对路径

**Response** (`RunFilePreviewResponse`):
```json
{
  "request_id": "d290f1ee-6c54-4b01-90e6-...",
  "run_id": "9d2c1f31-...",
  "path": "result/result.json",
  "preview": {
    "mode": "text",
    "content": "{\"status\":\"success\"}",
    "size": 20,
    "meta": "20 bytes, utf-8",
    "detected_format": "json",
    "rendered_html": "<div>...</div>",
    "json_pretty": "{\n  \"status\": \"success\"\n}"
  }
}
```

**错误码**:
- `400`: `path` 非法（绝对路径、包含 `..`、路径被过滤等）。
- `404`: `request_id`、run 或目标文件不存在。

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

返回 `text/event-stream`，用于实时消费 FCMP 单流对话事件。

**Query 参数**:
- `cursor`（可选，默认 `0`）：FCMP 续传游标（按 `chat_event.seq`）。

**事件类型**:
- `snapshot`：首帧快照，字段：`status`, `cursor`, `pending_interaction_id?`
- `chat_event`：FCMP 对话事件（`protocol_version=fcmp/1.0`）
- `heartbeat`：保活事件，字段：`ts`

**重连约定**:
- 客户端记录最近 `chat_event.seq`，重连时使用 `cursor`。
- 历史补偿通过 `/events/history` 拉取 FCMP 序列。

### 获取结构化历史事件
`GET /v1/jobs/{request_id}/events/history`

按区间拉取 FCMP 历史，适用于断线补偿与复盘。

**Query 参数**:
- `from_seq` / `to_seq`（可选）：按序号区间拉取
- `from_ts` / `to_ts`（可选）：按时间区间拉取（ISO8601）

### 获取引擎鉴权导入规格（管理 API）
`GET /v1/management/engines/{engine}/auth/import/spec`

用于 UI 渲染“导入鉴权文件”对话框。规则来自 engine adapter profile（声明式）。

**Query 参数**:
- `provider_id`（可选）：对 provider-aware engine（当前为 `opencode` / `qwen`）用于选择 provider-specific 导入规则。

**Response** (`ManagementEngineAuthImportSpecResponse`):
```json
{
  "engine": "qwen",
  "provider_id": "qwen-oauth",
  "supported": true,
  "ask_user": {
    "kind": "upload_files",
    "prompt": "Upload credential files to complete authentication.",
    "hint": "Select required files and submit to continue.",
    "files": [
      {
        "name": "oauth_creds.json",
        "required": true,
        "hint": "$HOME/.qwen/oauth_creds.json",
        "accept": ".json"
      }
    ],
    "ui_hints": {
      "risk_notice_required": false
    }
  }
}
```

**错误码**:
- `422`: 引擎/provider 不支持导入或导入规则非法。

**补充说明**:
- `qwen-oauth` 支持导入 `oauth_creds.json`。
- `qwen` 的 `coding-plan-china` / `coding-plan-global` 在当前版本不暴露导入式鉴权入口。

### 提交引擎鉴权文件导入（管理 API）
`POST /v1/management/engines/{engine}/auth/import`

**Request**:
- `Content-Type`: `multipart/form-data`
- `provider_id`（可选；对 provider-aware engine 用于选择导入规则）
- `files`（可重复）：鉴权文件

**Response** (`ManagementEngineAuthImportSubmitResponse`):
```json
{
  "engine": "qwen",
  "provider_id": "qwen-oauth",
  "imported_files": [
    {
      "source": "oauth_creds.json",
      "target_relpath": ".qwen/oauth_creds.json",
      "target_path": "/home/user/.qwen/oauth_creds.json"
    }
  ],
  "risk_notice_required": false
}
```

**错误码**:
- `422`: 缺少必需文件、结构校验失败、provider 不匹配等。

### 获取日志片段（raw_ref 回跳）
`GET /v1/jobs/{request_id}/logs/range`

按字节区间读取日志片段，供前端从结构化事件回跳原始证据。

**Query 参数**:
- `stream`：`stdout` / `stderr` / `pty`
- `byte_from`：起始字节偏移（含）
- `byte_to`：结束字节偏移（不含）
- `attempt`（可选，`>=1`）：指定恢复尝试轮次，默认使用最新轮次

### 对话事件流
`GET /v1/jobs/{request_id}/chat`

返回 `text/event-stream`，用于实时消费对话事件（与管理 API 的 `chat` 语义一致）。

**Query 参数**:
- `cursor`（可选，默认 `0`）：续传游标。

### 结构化对话历史
`GET /v1/jobs/{request_id}/chat/history`

按区间拉取对话历史。

**Query 参数**:
- `from_seq` / `to_seq`（可选）：按序号区间拉取
- `from_ts` / `to_ts`（可选）：按时间区间拉取（ISO8601）

### 鉴权会话（Auth Session）
`GET /v1/jobs/{request_id}/auth/session`

查询当前 run 关联的引擎鉴权会话状态。当 run 状态为 `waiting_auth` 时，客户端应使用此接口获取鉴权交互详情。

**Response**:
```json
{
  "request_id": "d290f1ee-...",
  "auth_session": {
    "session_id": "sess-abc-123",
    "engine": "codex",
    "transport": "oauth_proxy",
    "auth_method": "callback",
    "status": "waiting_callback",
    "auth_url": "https://login.microsoftonline.com/..."
  }
}
```

无关联鉴权会话时 `auth_session` 为 `null`。

说明：
- 该接口返回的是底层引擎鉴权会话状态，不等同于聊天侧 `pending_auth` 读模型。
- 会话型客户端在 `waiting_auth` 阶段通常需要同时读取：
  - `GET /v1/jobs/{request_id}/auth/session`
  - `GET /v1/jobs/{request_id}/interaction/pending`
- 某些 challenge 会自动推进而不接收聊天输入；这时 `pending_auth` 会表现为 `accepts_chat_input=false`、`input_kind=null`，前端应隐藏输入框并继续轮询。
- Claude 第三方 provider 配置场景会表现为 `transport=provider_config`、`auth_method=custom_provider`，其聊天侧 `pending_auth.challenge_kind/input_kind` 也都会是 `custom_provider`。

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
  - SSE 会推送 terminal `conversation.state.changed(to=canceled, data.terminal.error.code=CANCELED)`

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

内建 E2E 示例客户端是独立 FastAPI 服务（默认端口 `9814`），用于模拟真实前端调用链路，不复用 `/ui/*` 路由。

配置：
- `SKILL_RUNNER_E2E_CLIENT_PORT`：客户端端口，默认 `9814`；无效值回退到 `9814`。
- `SKILL_RUNNER_E2E_CLIENT_BACKEND_BASE_URL`：后端 API 地址，默认 `http://127.0.0.1:9813`。

主要页面与接口：
- `GET /`：读取并展示 Skill 列表。
- `GET /skills/{skill_id}/run`：按 schema 渲染输入页（engine/execution_mode/model + inline/parameter/file + runtime_options）。
- `POST /skills/{skill_id}/run`：提交执行（创建 run + 可选上传 zip）。
- `GET /runs/{request_id}`：运行观测页（stdout 主对话区、stderr 独立窗口、pending/reply 交互）。
- `GET /runs/{request_id}/result`：结果与产物展示页。
- `GET /api/runs/{request_id}/events`：按 `run_source` 代理后端 SSE（installed:`/v1/jobs/*`，temp:`/v1/temp-skill-runs/*`）。
- `POST /api/runs/{request_id}/reply`：代理后端 reply。

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

### System Console 页面
`GET /ui/settings`

返回 System Console 页面，提供日志级别配置、日志浏览（system/bootstrap）与数据重置等管理操作 GUI（后端通过 `/v1/management/system/*` 实现）。

### Engine 管理页面
`GET /ui/engines`

页面能力：
- 查看缓存化的 Engine 版本；
- 触发“升级全部”与“按引擎升级”；
- 跳转到 Engine 模型管理页。
- 鉴权交互收敛为“全局后台 + 引擎单入口菜单”：
  - 全局“鉴权后台”下拉：`oauth_proxy` / `cli_delegate`（默认 `oauth_proxy`）
  - 引擎表格每行一个“连接”入口；OpenCode 为 `provider -> 鉴权方式` 两级菜单
- 主鉴权状态区仅保留状态展示、输入区和“取消”按钮
- 在页面下方内嵌 TUI 终端（ttyd 网关）。
- 每个引擎提供“在内嵌终端中启动 TUI”按钮（同一时刻仅允许一个活跃会话）。
- sandbox 状态只在内嵌终端 banner 和 TUI 启动响应中展示，不再出现在 engine 表格中。
- Gemini 内嵌 TUI 在容器沙箱运行时可用时会显式追加 `--sandbox`（不可用时降级启动并保留状态提示）。
- 若 Gemini 当前认证模式是 API key（`security.auth.selectedType=gemini-api-key`），内嵌 TUI 会强制禁用 `--sandbox`，以避免该模式下 CLI 因 `GEMINI_API_KEY` 前置校验导致启动即退出。
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
- 容器部署时需显式映射 ttyd 端口（默认 `17681:17681`）。

兼容性说明：
- 旧页面 `GET /ui/engines/auth-shell` 已下线，返回 `404`。

### Engine 列表数据（Management Adapter）
`GET /ui/management/engines/table`

说明：
- `/ui/engines` 首屏直接服务端渲染表格。
- 该 partial 路由仅用于兼容局部刷新，不在首屏加载时触发版本探测。

兼容旧接口（已弃用）：
- `GET /ui/engines/table`

### Engine 鉴权交互 UI 接口

UI 层提供的引擎鉴权前端流程接口（代理后端 V2 Auth API）：
- `POST /ui/engines/auth/oauth-proxy/sessions`：启动 OAuth Proxy 鉴权会话
- `GET /ui/engines/auth/oauth-proxy/sessions/{session_id}`：查询 OAuth Proxy 会话状态
- `POST /ui/engines/auth/oauth-proxy/sessions/{session_id}/input`：提交用户输入
- `POST /ui/engines/auth/oauth-proxy/sessions/{session_id}/cancel`：取消会话
- `POST /ui/engines/auth/cli-delegate/sessions`：启动 CLI Delegate 鉴权会话
- `GET /ui/engines/auth/cli-delegate/sessions/{session_id}`：查询 CLI Delegate 会话状态
- `POST /ui/engines/auth/cli-delegate/sessions/{session_id}/input`：提交用户输入
- `POST /ui/engines/auth/cli-delegate/sessions/{session_id}/cancel`：取消会话

说明：这些 UI 接口为前端引擎鉴权提供 HTML 片段响应，内部代理 `/v1/engines/auth/*` V2 API。

### OpenCode 模型刷新
`POST /ui/engines/opencode/models/refresh`

触发 OpenCode 引擎模型列表的运行时探测缓存刷新，并返回 HTML 片段展示更新后的模型列表。

### Engine 模型快照管理（UI）
`POST /ui/engines/{engine}/models/snapshots`

通过 UI 表单新增当前检测版本的模型快照（代理 `POST /v1/engines/{engine}/models/snapshots`）。返回 HTML 片段用于页面局部刷新。

### Engine 升级状态轮询（HTML partial）
`GET /ui/engines/upgrades/{request_id}/status`

用于轮询展示升级任务状态，以及 per-engine 的 `action/stdout/stderr/error`。

### Engine 模型管理页面
`GET /ui/engines/{engine}/models`

页面能力：
- 查看当前 `manifest.json`、解析到的快照、模型列表；
- 通过表单新增“当前检测版本”的模型快照（add-only）。

### Run 观测页面
`GET /ui/runs`

页面能力：
- 按 `request_id` 展示 run 列表（关联 `run_id`）；
- 列表按页展示（默认 20 条/页），并支持“进入详情后返回原分页”；
- 列表包含 `model` 列；
- 展示当前状态、`pending_interaction_id`、`interaction_count`、`recovery_state` 与更新时间；
- 轮询建议遵循 `poll_logs`：`queued/running=true`，`waiting_user=false`；
- 支持自动刷新列表。

### Run 列表数据（Management Adapter）
`GET /ui/management/runs/table`

Query 参数：
- `page`（可选，默认 `1`）
- `page_size`（可选，默认 `20`）

兼容旧接口（已弃用）：
- `GET /ui/runs/table`

### Run 详情页面（对话窗口）
`GET /ui/runs/{request_id}`

页面能力：
- 展示 request/run 基本信息；
- run 动作区包含并列 `Download Bundle` 与 `Download Debug Bundle` 按钮（仅成功终态可用）；
- 展示 run 文件树（只读）与文件预览；文件区采用最大高度约束并在区内滚动；
- 通过 SSE 实时查看输出：主对话优先消费 `chat_event`（FCMP），并将诊断/原始日志分区展示；
- 支持 `raw_ref` 回跳：从结构化消息定位并预览原始日志区间；
- 提供结构化事件关联视图（按 `seq/correlation` 浏览）；
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
  "cache_hit": false,
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

### 查询临时运行结果/产物/Bundle/日志/对话/取消
- `GET /v1/temp-skill-runs/{request_id}/result`
- `GET /v1/temp-skill-runs/{request_id}/artifacts`
- `GET /v1/temp-skill-runs/{request_id}/bundle`
- `GET /v1/temp-skill-runs/{request_id}/logs`
- `GET /v1/temp-skill-runs/{request_id}/logs/range`（支持 `stream`、`byte_from`、`byte_to`、`attempt` 参数）
- `GET /v1/temp-skill-runs/{request_id}/events`
- `GET /v1/temp-skill-runs/{request_id}/events/history`
- `GET /v1/temp-skill-runs/{request_id}/chat`（SSE 对话事件流）
- `GET /v1/temp-skill-runs/{request_id}/chat/history`（结构化对话历史）
- `GET /v1/temp-skill-runs/{request_id}/auth/session`（鉴权会话状态查询）
- `POST /v1/temp-skill-runs/{request_id}/cancel`

语义与 `/v1/jobs/*` 对齐，但作用范围仅限临时 skill 的这次请求。
缓存策略与常规链路一致：
- `runtime_options.execution_mode=auto` 且 `no_cache!=true`：允许 cache lookup 与 write-back。
- `runtime_options.execution_mode=interactive`：不读 cache，也不回写 cache。
- `runtime_options.no_cache=true`：无论模式，均禁用 cache lookup 与 write-back。
- 临时 skill 的 auto 缓存键额外包含“上传 skill 压缩包整体哈希”，避免不同包误命中。

### 临时 Skill 包校验规则（严格）
- Zip 必须且只能有一个顶层目录（顶层目录名即 `skill_id`）。
- 禁止 zip-slip/绝对路径条目（包含 `..`、绝对路径、盘符前缀等）。
- 必须包含并可解析：
  - `SKILL.md`
  - `assets/runner.json`
  - `runner.json.schemas` 指向的 `input` / `parameter` / `output` 三个 schema 文件
- 身份一致性：顶层目录名、`runner.json.id`、`SKILL.md` frontmatter `name` 必须一致。
- 元数据约束：`runner.json.engines` 可选、`runner.json.unsupported_engines` 可选；若同时声明则不允许重复且计算后的有效引擎集合必须非空。`runner.json.artifacts` 可选（若提供需为数组）。
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
    {"engine": "opencode", "cli_version_detected": "0.1.0"},
    {"engine": "claude", "cli_version_detected": "0.1.0"},
    {"engine": "qwen", "cli_version_detected": "0.1.0"}
  ]
}
```

### 引擎鉴权会话接口（受 Basic Auth 保护）
V2（transport 分组）：
- `POST /v1/engines/auth/oauth-proxy/sessions`
- `GET /v1/engines/auth/oauth-proxy/sessions/{session_id}`
- `POST /v1/engines/auth/oauth-proxy/sessions/{session_id}/input`
- `POST /v1/engines/auth/oauth-proxy/sessions/{session_id}/cancel`
- `GET /v1/engines/auth/oauth-proxy/callback/openai`（免 Basic Auth）
- `POST /v1/engines/auth/cli-delegate/sessions`
- `GET /v1/engines/auth/cli-delegate/sessions/{session_id}`
- `POST /v1/engines/auth/cli-delegate/sessions/{session_id}/input`
- `POST /v1/engines/auth/cli-delegate/sessions/{session_id}/cancel`

兼容层（deprecated）：
- `POST /v1/engines/auth/sessions`
- `GET /v1/engines/auth/sessions/{session_id}`
- `POST /v1/engines/auth/sessions/{session_id}/input`
- `POST /v1/engines/auth/sessions/{session_id}/cancel`

V2 `start` 请求体示例：
```json
{
  "engine": "codex",
  "auth_method": "callback",
  "transport": "oauth_proxy"
}
```

provider-aware 示例：
```json
{
  "engine": "qwen",
  "provider_id": "qwen-oauth",
  "auth_method": "auth_code_or_url",
  "transport": "oauth_proxy"
}
```

说明：
- `transport` 支持 `oauth_proxy` 与 `cli_delegate`。
- V2 下 `auth_method` 为必填；公开引擎鉴权接口当前支持 `callback` / `auth_code_or_url` / `api_key`，而会话内 provider-config 路径还会使用 `custom_provider`。
- 旧值 `browser-oauth/device-auth/screen-reader-google-oauth/iflow-cli-oauth/opencode-provider-auth` 已废弃并返回 `422`；`iflow` 引擎本身已不再作为活跃支持引擎提供。
- V2 下不再使用 `method` 历史字段；兼容层仍可接收 `method`。
- provider-aware engine（当前为 `opencode`、`qwen`）应显式提交 `provider_id`；这也是新的推荐写法。
- `codex` 支持 2x2 组合：`oauth_proxy|cli_delegate` × `callback|auth_code_or_url`。
- `gemini` 支持：
  - `oauth_proxy + callback`（自动回调优先，零 CLI，支持 `/input` 兜底）
  - `oauth_proxy + auth_code_or_url`（手工码流，需 `/input`）
  - `cli_delegate + auth_code_or_url`（现有 CLI 委托链路）
- `opencode(provider_id=openai)` 支持 2x2：`oauth_proxy|cli_delegate` × `callback|auth_code_or_url`。
- `opencode(provider_id=google)` 支持：
  - `oauth_proxy + callback`（自动回调）
  - `oauth_proxy + auth_code_or_url`（手工回填）
  - `cli_delegate + auth_code_or_url`（现有 CLI 编排）
- `qwen(provider_id=qwen-oauth)` 支持：
  - `oauth_proxy + auth_code_or_url`（设备码语义，返回 `auth_url + user_code`；当前实现会自动轮询完成状态，不要求额外 `/input`）
  - `cli_delegate + auth_code_or_url`（CLI 自行轮询完成状态，不要求额外 `/input`）
- `qwen(provider_id=coding-plan-china|coding-plan-global)` 支持：
  - `oauth_proxy + api_key`
  - `cli_delegate + api_key`
- `cli_delegate + codex` 映射：
  - `callback` -> `codex login`
  - `auth_code_or_url` -> `codex login --device-auth`
- provider-aware engine 在 V2 通过 `provider_id + auth_method` 指定流程。
- 仅在会话确实需要用户输入时，才通过 `/input` 回填；`kind` 支持 `code` / `api_key` / `text`。
- `auth_code_or_url` 表示统一的“人工 OAuth 返回内容”语义，不等于一定会显示输入框；是否需要输入以会话返回的 `input_kind` / `accepts_chat_input` 为准。
- 会话快照包含 `transport_state_machine`、`orchestrator`、`log_root` 用于状态解释与日志定位。
- 语义约束：
  - `oauth_proxy` 不应出现 `waiting_orchestrator`
  - `cli_delegate` 不应出现 `polling_result`

OpenAI OAuth 代理回调说明：
- 默认 `redirect_uri` 为 `http://localhost:1455/auth/callback`。
- 服务会在 OpenAI OAuth 会话启动时按需拉起本地回调监听（`127.0.0.1:1455`）用于自动收口，会话结束后释放端口。
- `callback` 模式支持 `/input` 作为兜底（远程部署本地回调不可达时可手工粘贴回调 URL 或 code）。

OpenCode Google（Antigravity）OAuth 代理说明：
- `oauth_proxy + opencode(provider_id=google)` 使用固定回调地址 `http://localhost:51121/oauth-callback`。
- 会话启动时服务按需拉起本地 listener（`127.0.0.1:51121`），会话终止时释放。
- `callback` 模式支持 `/input` 兜底；`auth_code_or_url` 模式可通过 `/input(kind=text)` 提交 redirect URL 或 code。
- 需通过环境变量提供 Google OAuth 凭据：
  - `SKILL_RUNNER_OPENCODE_GOOGLE_OAUTH_CLIENT_ID`
  - `SKILL_RUNNER_OPENCODE_GOOGLE_OAUTH_CLIENT_SECRET`

Gemini OAuth 代理说明：
- `oauth_proxy + gemini` 使用本地回调地址 `http://localhost:51122/oauth2callback`。
- 会话启动时服务按需拉起本地 listener（`127.0.0.1:51122`），会话终止时释放。
- `callback` 模式要求本地 listener 可用，并支持 `/input` 兜底。
- `auth_code_or_url` 模式使用手工码流，通过 `/input(kind=text|code)` 完成鉴权。
- 鉴权成功后会写入 `~/.gemini/oauth_creds.json`（以及可选 `google_accounts.json`），并确保 `~/.gemini/settings.json` 中 `security.auth.selectedType="oauth-personal"`。

Qwen OAuth / Coding Plan 说明：
- `oauth_proxy + qwen(provider_id=qwen-oauth)` 走设备码语义，返回 `auth_url + user_code`；当前实现会在后端自动轮询完成状态，不要求用户额外调用 `/input`。
- `qwen-oauth` 鉴权成功后写入 `.qwen/oauth_creds.json`。
- `coding-plan-china` / `coding-plan-global` 通过 API Key 完成，会写入 `.qwen/settings.json`。
- `qwen` 当前没有公开的 browser callback 端点；`qwen-oauth` 的 `oauth_proxy` 不是本地回调模式。
- 不读写 `mcp-oauth-tokens-v2.json`。
- 需通过环境变量提供 Google OAuth 凭据：
  - `SKILL_RUNNER_GEMINI_OAUTH_CLIENT_ID`
  - `SKILL_RUNNER_GEMINI_OAUTH_CLIENT_SECRET`

Claude bootstrap / runtime 配置说明：
- Claude 的 bootstrap 默认值写入 `~/.claude.json`，而不是 `~/.claude/settings.json`。
- bootstrap 目前会初始化：
  - `hasCompletedOnboarding = true`
- Claude 的每次运行仍会生成 run-local `run_dir/.claude/settings.json`，用于本次 run 的环境变量和模型注入。
- 这两层文件职责不同：
  - `~/.claude.json`：agent-home 全局状态
  - `run_dir/.claude/settings.json`：单次运行配置
- Claude headless run / harness 的运行姿态：
  - `permissions.defaultMode = "bypassPermissions"`
  - `sandbox.enabled = true`
  - `sandbox.allowUnsandboxedCommands = false`
  - sandbox 文件写权限动态约束到 `run_dir`
  - Claude sandbox 依赖 `bubblewrap`（`bwrap`）和 `socat`
  - 官方容器镜像默认以非 root 用户运行；Claude container/headless 支持依赖这一前提
  - 缺少依赖、sandbox 初始化失败或运行期命令被 sandbox 拦截时，会产生明确的 diagnostics / warnings
  - 这些告警不会单独把 preflight 或 run 变成硬失败
- Claude inline UI shell 与 headless run 分治：
  - 使用独立的 session-local `.claude/settings.json`
  - `permissions.defaultMode = "dontAsk"`
  - 默认只保留轻量网络交互，文件编辑与 shell 类工具默认禁用

服务端回调端点（免 Basic Auth）：
- `GET /v1/engines/auth/oauth-proxy/callback/openai`
- `GET /v1/engines/auth/callback/openai`（兼容）
- `GET /auth/callback`（兼容别名）

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
      "provider": "openai",
      "provider_id": "openai",
      "model": "gpt-5.2-codex",
      "display_name": "GPT-5.2 Codex",
      "deprecated": false,
      "notes": "pinned snapshot",
      "supported_effort": ["low", "medium", "high", "xhigh"]
    }
  ]
}
```

说明：
- 同一模型项结构也用于 `GET /v1/management/engines/{engine}` 的 `models[]`。
- 新客户端应优先读取 `provider_id + model + supported_effort`；`id` 保留兼容语义。
- 单 provider 引擎的 `provider_id` 固定为 canonical provider：
  - `codex -> openai`
  - `gemini -> google`

OpenCode 返回示例（动态探测缓存）：
```json
{
  "engine": "opencode",
  "cli_version_detected": "0.1.0",
  "snapshot_version_used": "2026-02-25T00:00:00Z",
  "source": "runtime_probe_cache",
  "fallback_reason": null,
  "models": [
    {
      "id": "openai/gpt-5",
      "provider": "openai",
      "provider_id": "openai",
      "model": "gpt-5",
      "display_name": "OpenAI GPT-5",
      "deprecated": false,
      "notes": "runtime_probe_cache",
      "supported_effort": ["default", "low", "medium", "high"]
    }
  ]
}
```

Qwen 返回示例（静态 snapshot）：
```json
{
  "engine": "qwen",
  "cli_version_detected": "0.1.0",
  "snapshot_version_used": "0.0.0",
  "source": "pinned_snapshot",
  "fallback_reason": null,
  "models": [
    {
      "id": "qwen3-coder-plus",
      "provider": "coding-plan-global",
      "provider_id": "coding-plan-global",
      "model": "qwen3-coder-plus",
      "display_name": "Qwen3-Coder Plus",
      "deprecated": false,
      "notes": "Alibaba Cloud Coding Plan (Global)",
      "supported_effort": ["default"]
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

OpenCode 兼容视图说明：
- 返回动态缓存兼容结构（`manifest.dynamic=true`、`manifest.source=runtime_probe_cache`）。
- `resolved_snapshot_file` 指向本地缓存文件名（默认 `opencode_models_cache.json`）。
- 不要求存在 `server/engines/opencode/models/manifest.json` 快照文件。

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
- `engine=opencode` 明确不支持该写接口，返回 `409 Conflict`。

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
    "codex": {"status": "succeeded", "action": "upgrade", "stdout": "...", "stderr": "", "error": null},
    "gemini": {"status": "failed", "action": "install", "stdout": "...", "stderr": "...", "error": "Install command exited with code 1"},
    "opencode": {"status": "succeeded", "action": "upgrade", "stdout": "...", "stderr": "", "error": null}
  },
  "created_at": "2026-02-12T10:00:00.000000",
  "updated_at": "2026-02-12T10:00:12.000000"
}
```

说明：
- 单 engine 任务在 managed prefix 缺失时，会自动走 `action=install`；
- 单 engine 任务在 managed prefix 已存在时，走 `action=upgrade`；
- `mode=all` 仍按升级语义处理。
