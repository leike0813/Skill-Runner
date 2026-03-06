# Agent Skill Runner（REST）开发文档
Version: v0.3+

================================================================================
0. 项目一句话定义
================================================================================
实现一个本地/自托管的 REST 服务（Agent Skill Runner），用于以统一 API 方式调用成熟商用/社区 CLI agent 工具（Codex、Gemini CLI、iFlow CLI、OpenCode）执行"完全自动化 skill"或"interactive 多轮会话 skill"，并返回严格结构化的结果（满足 output schema）与产物（artifacts）。Runner 负责执行编排、会话状态管理、输出校验与必要的规范化，不为 skill 的业务正确性背书。

内建 Web UI 提供 Skill 管理、Run 执行/监控、引擎管理与鉴权等界面。

================================================================================
1. 核心需求（已实现）
================================================================================
R1. REST API 暴露 ✅
- FastAPI 暴露 REST API；支持同步（短任务）与异步（长任务）两种模式。
- 分层路由：Domain API (`/v1/management/*`) + Execution API (`/v1/jobs*`、`/v1/skills*` 等) + UI Adapter (`/ui/*`)。

R2. Skill 可插拔 ✅
- Skills 以"包"形式管理：通过 `POST /v1/skill-packages/install` 上传安装，或通过 `POST /v1/temp-skill-runs` 临时上传执行。
- Skill 包必须提供 `input.schema.json`、`parameter.schema.json`、`output.schema.json`。
- Skill 包必须声明 `runner.json`（AutoSkill Manifest），包含引擎支持列表、执行模式、artifacts 合同等。
- 服务端对上传包执行 meta-schema 预检。

R3. 多引擎支持 ✅（4 引擎全部落地）
- Codex（`server/engines/codex/`）
- Gemini（`server/engines/gemini/`）
- iFlow（`server/engines/iflow/`）
- OpenCode（`server/engines/opencode/`）
- 统一 `BaseExecutionAdapter` 接口（详见 §6）；引擎特定逻辑封装在各自子类中。

R4. 输出稳定性：验证 + 规范化 ✅
- 输出校验使用 output.schema.json + jsonschema；不合法时进入解析/规范化链。
- 详见 §7。

R5. Artifacts 一等公民 ✅
- 产物扫描、sha256 索引、manifest.json 生成。
- 通过 `/v1/jobs/{request_id}/bundle` 下载 bundle zip。
- 详见 §8。

R6. 自动化与非交互 / Interactive ✅
- 同时支持 `auto`（全自动）与 `interactive`（多轮交互）执行模式。
- 强制超时、取消（kill 子进程）。
- 日志与事件记录：FCMP 事件协议（见 §6 interactive 会话机制）。

================================================================================
2. 非目标（明确不做）
================================================================================
N1. 不实现"自定义模型/自建agent平台"
N2. 不保证 skill 的业务正确性，只保证执行与结构化输出合同
N3. 不做复杂权限系统（已实现 OAuth 鉴权流用于引擎 CLI 认证，但不做多租户/RBAC）
N4. 不实现分布式队列/多节点（单机运行）

================================================================================
3. 总体架构
================================================================================
系统采用 4 层架构。详细组件清单见 `docs/core_components.md`，项目目录结构见 `docs/project_structure.md`。

### Runtime Layer（`server/runtime/`）
底层执行基础设施，不依赖上层 Services。

| 子包 | 职责 |
|------|------|
| `runtime/adapter/` | `BaseExecutionAdapter` 及其统一类型定义（`AdapterTurnResult`、`contracts.py`） |
| `runtime/session/` | 会话状态机（`statechart.py`）、超时管理（`timeout.py`） |
| `runtime/protocol/` | FCMP 事件协议（`event_protocol.py`）、Schema Registry、协议解析工具 |
| `runtime/observability/` | Run 可观测性（`run_observability.py`）、数据源适配（`run_source_adapter.py`）、读取门面（`run_read_facade.py`） |
| `runtime/auth/` | 鉴权驱动注册表（`driver_registry.py`）、OAuth 回调（`callbacks.py`）、会话生命周期（`session_lifecycle.py`） |

### Services Layer（`server/services/`）
中层业务编排，依赖 Runtime 提供的抽象。

| 子包 | 职责 |
|------|------|
| `services/orchestration/` | `JobOrchestrator`、`RunStore`（sqlite）、`WorkspaceManager`、`RunStateService`、`RunProjectionService` 等 |
| `services/engine_management/` | `EngineAdapterRegistry`、`EngineAuthFlowManager`、`ModelRegistry`、`EngineUpgradeManager`、`AgentCliManager` 等 |
| `services/platform/` | `SchemaValidator`（JSON Schema 校验）、`ConcurrencyManager`、`OptionsPolicy`、`CacheManager` |
| `services/skill/` | `SkillRegistry`、`SkillPackageManager`（安装/卸载）、`SkillPackageValidator`、`SkillPatcher`（运行时补丁）、`TempSkillRunManager` |

### Engines Layer（`server/engines/`）
各引擎的 `BaseExecutionAdapter` 子类 + 引擎特有逻辑。

| 子包 | 包含 |
|------|------|
| `engines/codex/` | `CodexAdapter`、配置融合、OAuth 代理 |
| `engines/gemini/` | `GeminiAdapter`、OAuth 流程 |
| `engines/iflow/` | `IFlowAdapter`、OAuth 流程 |
| `engines/opencode/` | `OpenCodeAdapter`、鉴权存储、OAuth 代理 |
| `engines/common/` | 跨引擎共享逻辑（如 OpenAI-compatible SSOT） |

### Routers Layer（`server/routers/`）
HTTP 路由入口。

| 文件 | 路由前缀 | 职责 |
|------|----------|------|
| `skills.py` | `/v1/skills` | Skill 元数据查询 |
| `jobs.py` | `/v1/jobs` | 提交执行、状态查询、结果/Bundle/日志/事件/交互 |
| `engines.py` | `/v1/engines` | 引擎状态、模型列表、鉴权管理、升级 |
| `management.py` | `/v1/management` | Domain API：skill/engine/run 管理聚合接口 |
| `skill_packages.py` | `/v1/skill-packages` | Skill 包安装流程 |
| `temp_skill_runs.py` | `/v1/temp-skill-runs` | 临时 skill 上传并执行 |
| `ui.py` | `/ui` | 内建 Web UI 页面渲染 |
| `oauth_callback.py` | `/auth/callback` | OAuth 回调端点 |

================================================================================
4. 工作区（Workspace）约定
================================================================================
### 请求目录（`data/requests/<request_id>/`）
```
data/requests/<request_id>/
  uploads/                 # 客户端上传的 input 文件
```

### Run 目录（`data/runs/<run_id>/`）
```
data/runs/<run_id>/
  .state/
    state.json             # run 当前状态真相（唯一 current truth）
    dispatch.json          # queued 内部 dispatch 生命周期真相
  .audit/
    request_input.json     # 请求输入快照（仅审计/回放）
    stdout.<N>.log         # 第 N 次 attempt 的 stdout
    stderr.<N>.log         # 第 N 次 attempt 的 stderr
    stdin.<N>.log          # 第 N 次 attempt 的 stdin
    pty-output.<N>.log     # PTY 输出（部分引擎）
    events.<N>.jsonl       # 引擎事件流
    fcmp_events.<N>.jsonl  # FCMP 协议事件
    orchestrator_events.<N>.jsonl  # 编排器事件
    parser_diagnostics.<N>.jsonl   # 协议解析诊断
    protocol_metrics.<N>.json      # 协议指标
    fs-before.<N>.json     # 执行前文件系统快照
    fs-after.<N>.json      # 执行后文件系统快照
    fs-diff.<N>.json       # 文件系统差异
    meta.<N>.json          # attempt 元信息
  result/
    result.json            # 最终结构化结果（满足 output_schema）
  artifacts/               # skill 产物（初始为空目录）
  .<engine>/               # 引擎隔离工作区
    skills/<skill_id>/     # skill 包副本（安装到引擎目录）
    ...                    # 引擎配置文件（settings.json / config.toml 等）
  bundle/                  # 产物打包（执行完成后生成）
    manifest.json          # artifacts 索引（role/path/mime/sha256/size）
    manifest_debug.json    # 含调试信息的索引
    run_bundle.zip         # 标准 bundle
    run_bundle_debug.zip   # 含调试信息的 bundle
```

写入策略：
- Adapter 写入 `.audit/`（stdout/stderr/events 等，按 attempt 编号）
- `RunStateService` 写入 `.state/state.json`、`.state/dispatch.json`、`result/result.json`
- Bundle 生成器写入 `bundle/`
- Skill 仅可写 `artifacts/`（通过引擎工作区间接写入）

================================================================================
5. Skill 包结构与规范
================================================================================
### 5.1 标准要求（Agent Skills Spec 兼容）
一个 skill 是一个目录，至少包含 `SKILL.md`：
```
skill-name/
└── SKILL.md          # 必需：YAML frontmatter + Markdown 指令正文
```

SKILL.md frontmatter 必需字段：
- `name`：1-64 字符，小写字母/数字/连字符，必须与目录名一致
- `description`：1-1024 字符

可选字段：`license`、`compatibility`、`metadata`

可选目录（标准推荐）：
- `scripts/`：可执行代码
- `references/`：补充文档
- `assets/`：静态资源

### 5.2 AutoSkill Profile（Runner 扩展约束）
Runner 所需的"自动化执行合同"放在 `assets/` 中：

```
skill-name/
├── SKILL.md
├── assets/
│   ├── runner.json              # 必需：AutoSkill Manifest（见 5.3）
│   ├── input.schema.json        # 必需：文件输入 JSON Schema
│   ├── parameter.schema.json    # 必需：参数 JSON Schema
│   ├── output.schema.json       # 必需：输出 JSON Schema
│   ├── codex_config.toml        # 可选：Codex CLI 推荐配置
│   ├── gemini_settings.json     # 可选：Gemini CLI 推荐配置
│   ├── iflow_settings.json      # 可选：iFlow CLI 推荐配置
│   └── opencode.json            # 可选：OpenCode 推荐配置
├── scripts/                     # 可选
└── references/                  # 可选
```

### 5.3 AutoSkill Manifest（`assets/runner.json`）
```json
{
  "id": "skill-name",
  "version": "1.0.0",
  "engines": ["codex", "gemini", "iflow", "opencode"],
  "unsupported_engines": [],
  "execution_modes": ["auto", "interactive"],
  "entrypoint": {
    "type": "prompt|script|hybrid",
    "prompt": {
      "template": "assets/prompt.txt",
      "result_mode": "file|stdout",
      "result_file": "result/result.json"
    }
  },
  "schemas": {
    "input": "assets/input.schema.json",
    "parameter": "assets/parameter.schema.json",
    "output": "assets/output.schema.json"
  },
  "artifacts": [
    {
      "role": "notes_md",
      "pattern": "artifacts/notes.md",
      "mime": "text/markdown",
      "required": false
    }
  ],
  "automation": {
    "timeout_sec": 600,
    "network": "off|allowlist",
    "allowlist": [],
    "fs_scope": "workspace_only"
  },
  "max_attempt": 3
}
```

说明：
- `engines` 可选；缺失时按"系统支持的全部引擎"处理。
- `unsupported_engines` 可选；用于从允许集合中剔除。有效集合 = (engines 或全量) - unsupported_engines。
- `execution_modes` 必填，值仅允许 `auto`/`interactive`。
- `max_attempt` 可选正整数（≥1），仅作用于 interactive 模式。
- Schema 文件在上传阶段执行 meta-schema 预检（如 `x-input-source`、`x-type` 扩展字段）。

### 5.4 Skill 包安装与临时执行
- **安装**：`POST /v1/skill-packages/install` 上传 zip/tar.gz → 解压、校验、注册到 `SkillRegistry`。
- **临时执行**：`POST /v1/temp-skill-runs` 上传后直接创建 run，执行完成后可选清理。
- **Skill Patcher**（`server/services/skill/skill_patcher.py`）：运行时对 skill 包内容进行补丁（如注入输出约束、重定向产物路径）。

================================================================================
6. 引擎适配（BaseExecutionAdapter）统一接口
================================================================================
详细设计见 `docs/adapter_design.md`。

### 6.1 统一 5 阶段管线
所有引擎适配器继承 `BaseExecutionAdapter`（`server/runtime/adapter/base_execution_adapter.py`），实现统一的 5 阶段管线：

```
_construct_config(skill, run_dir, options) → Path
    ↓ 合并 default + skill_recommended + user_options + enforced 配置
_setup_environment(skill, run_dir) → None
    ↓ 工作区环境准备（skill 副本安装、配置注入等）
_build_prompt(skill, run_dir, input_data) → str
    ↓ Jinja2 模板渲染 + 文件引用解析
_execute_process(cmd, run_dir, env) → (exit_code, stdout, stderr)
    ↓ 异步子进程执行 + 超时控制
_parse_output(raw_stdout) → AdapterTurnResult
    ↓ 从原始输出中提取结构化结果
```

方法签名：
- `_construct_config(self, skill: SkillManifest, run_dir: Path, options: dict[str, Any]) → Path`
- `_setup_environment(self, skill: SkillManifest, run_dir: Path) → None`
- `_build_prompt(self, skill: SkillManifest, run_dir: Path, input_data: dict[str, Any]) → str`
- `async _execute_process(self, cmd: list[str], run_dir: Path, env: dict[str, str]) → tuple[int, str, str]`
- `_parse_output(self, raw_stdout: str) → AdapterTurnResult`

### 6.2 配置加载逻辑（Config Fusion）
4 层配置合并，优先级从低到高：

| 层级 | 来源 | 路径示例 |
|------|------|----------|
| 1. Engine Default | `server/engines/<engine>/config/default.*` | `server/engines/codex/config/default.toml` |
| 2. Skill Recommended | `assets/<engine>_config.*` 或 `assets/<engine>_settings.json` | skill 包内 |
| 3. User Options | API 参数：`model` + `runtime_options` + `<engine>_config` | 请求体 |
| 4. Enforced Config | `server/engines/<engine>/config/enforced.*` | `server/engines/codex/config/enforced.toml` |

各引擎配置写入位置：
- Codex：`run_dir/.codex/` 下的配置
- Gemini：`run_dir/.gemini/settings.json`
- iFlow：`run_dir/.iflow/settings.json`
- OpenCode：`run_dir/opencode.json`，按模式覆盖 `permission.question`（auto=deny, interactive=allow）

### 6.3 各引擎策略

**CodexAdapter**：
- 使用 `codex exec --json` 执行；支持 `--resume` 恢复 interactive 会话。
- Session Handle 来源：首条 `thread.started.thread_id`。

**GeminiAdapter**：
- Skill 目录复制到 `run_dir/.gemini/skills/<skill_id>`。
- 配置 `experimental.skills=true`。
- 使用 Invocation Prompt 调用 skill。
- Session Handle 来源：JSON 返回体 `session_id`。

**IFlowAdapter**：
- 类似 Gemini 的 skill 安装 + invocation 模式。
- Session Handle 来源：`<Execution Info>` 中 `session-id`。

**OpenCodeAdapter**：
- 配置文件 `opencode.json` 写入 run_dir。
- 按执行模式设置 `permission.question`（auto=deny, interactive=allow）。
- 支持 Google 和 OpenAI 双 OAuth 代理鉴权。

### 6.4 Interactive 会话机制
详细状态机定义见 `docs/session_runtime_statechart_ssot.md`。

- 统一为单一可恢复会话范式（single resumable），不再区分双档位。
- Orchestrator 在 interactive 首回合前完成恢复能力探测，走统一可恢复路径并持久化 `EngineSessionHandle`。
- 自动回复开关：`runtime_options.interactive_auto_reply`（默认 `false`）。
- Interactive 完成判定（双轨）：
  - 强条件：assistant 回复中检测到 `__SKILL_DONE__`。
  - 软条件：未检测到 marker，但当轮输出通过 output schema（记录 warning `INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER`）。
  - `tool_use`/tool 回显中的 marker 文本不参与完成判定。
- ask_user 提示建议采用 YAML 并包裹 `<ASK_USER_YAML>...</ASK_USER_YAML>`。
- 超时：`runtime_options.interactive_reply_timeout_sec`（默认 1200 秒）。
- `max_attempt`：当 `attempt_number >= max_attempt` 且未完成时，返回 `INTERACTIVE_MAX_ATTEMPT_EXCEEDED`。

### 6.5 服务启动期恢复（Startup Reconciliation）
- 扫描非终态 run：`queued/running/waiting_user`。
- `waiting_user`：校验 `pending_interaction_id + session handle`，有效则保持 waiting；无效则 `SESSION_RESUME_FAILED`。
- `queued/running`：收敛为 `failed`，错误码 `ORCHESTRATOR_RESTART_INTERRUPTED`。
- 恢复观测字段：`recovery_state`、`recovered_at`、`recovery_reason`。

================================================================================
7. 输出校验与规范化链
================================================================================
### 解析阶段（Parse）
- 优先读取 `run_dir/result/result.json`（若存在）。
- 否则从 stdout 中提取 JSON：去除 code fence 包裹、提取第一个合法 JSON 对象。
- 解析结果封装为 `AdapterTurnResult`（`server/runtime/adapter/types.py`）。

### 校验阶段（Validate）
- 使用 `output.schema.json` + jsonschema 校验。
- 通过：进入 artifacts 索引。
- 失败：进入规范化链。

### 规范化链（Normalize Pipeline）
N0 Deterministic Normalize（runner 内置）
- 去 fence、trim、修复常见格式问题（仅语法层）。

N1 Skill Normalizer（可选）
- 若 `runner.json` 声明 `normalizer.command`：执行该脚本。
- 输入：raw 输出 + schema 路径 + workspace。
- 输出：`result/result.json`。

N2 Skill Fallback（可选，非LLM）
- 若声明 `fallback.command`：执行 fallback 脚本。

### 最终失败
- 返回结构化错误响应：`validation_errors`、`raw_output_path`。
- 响应必须包含 warnings（如发生规范化/降级）：`warnings[]: {code, message, level, normalization_level, details}`。

================================================================================
8. Artifacts 管理与返回
================================================================================
Artifact 索引规则：
- 依据 `runner.json` artifacts 合同扫描 `artifacts/` 目录。
- 对每个匹配文件计算 sha256、size、mime（后缀映射）。
- 生成 `bundle/manifest.json`：
  ```json
  {
    "artifacts": [
      {"role": "...", "path_rel": "...", "filename": "...", "mime": "...", "size": 0, "sha256": "...", "required": false}
    ]
  }
  ```
- 同时生成 `bundle/manifest_debug.json`（含调试信息）。
- 打包为 `bundle/run_bundle.zip` 和 `bundle/run_bundle_debug.zip`。

下载：
- `GET /v1/jobs/{request_id}/bundle` — 下载标准 bundle zip。
- `GET /v1/jobs/{request_id}/artifacts` — 返回 artifacts 列表。
- `GET /v1/jobs/{request_id}/artifacts/{path}` — 下载单个产物文件。

================================================================================
9. REST API 设计（v1）
================================================================================
- Base URL: `http://127.0.0.1:<port>/v1`
- 所有请求/响应 JSON，UTF-8
- 响应按各接口的 Response Model 返回

### 分层约定
- **Domain API**（推荐）：`/v1/management/*` — 面向任意前端，稳定 JSON 语义。
- **Execution API**（兼容）：`/v1/jobs*`、`/v1/skills*`、`/v1/engines*`、`/v1/temp-skill-runs*`、`/v1/skill-packages*` — 保留执行链路与历史契约。
- **UI Adapter**：`/ui/*` — 内建 Web UI 页面渲染与交互。
- **OAuth Callback**：`/auth/callback` — 引擎 OAuth 回调。

### Management API（`server/routers/management.py`）
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/v1/management/skills` | Skill 列表（SkillSummary） |
| GET | `/v1/management/skills/{skill_id}` | Skill 详情 |
| GET | `/v1/management/skills/{skill_id}/schemas` | input/parameter/output schema 内容 |
| GET | `/v1/management/engines` | 引擎列表（缓存版本 + models_count） |
| GET | `/v1/management/engines/{engine}` | 引擎详情（不含 auth/sandbox 摘要） |
| GET | `/v1/management/runs` | 运行记录列表 |
| GET | `/v1/management/runs/{request_id}` | 运行对话状态（RunConversationState） |
| GET | `/v1/management/runs/{request_id}/files` | 运行文件树 |
| GET | `/v1/management/runs/{request_id}/file?path=…` | 文件预览（路径越界保护） |
| GET | `/v1/management/runs/{request_id}/events` | SSE 实时流（FCMP 单流） |
| GET | `/v1/management/runs/{request_id}/events/history` | 结构化历史事件回放 |
| GET | `/v1/management/runs/{request_id}/protocol/history` | 协议历史事件 |
| GET | `/v1/management/runs/{request_id}/logs/range` | 日志区间读取 |
| GET | `/v1/management/runs/{request_id}/pending` | 查询当前待决交互 |
| POST | `/v1/management/runs/{request_id}/reply` | 提交交互回复 |
| POST | `/v1/management/runs/{request_id}/cancel` | 取消运行 |
| GET | `/v1/management/system/settings` | 读取 Settings 页面所需的系统设置视图 |
| PUT | `/v1/management/system/settings` | 更新可写日志设置并热重载 |
| POST | `/v1/management/system/reset-data` | 高危：重置项目数据库与落盘数据（需确认文本） |

### Skills API（`server/routers/skills.py`）
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/v1/skills` | 技能列表 |
| GET | `/v1/skills/{skill_id}` | SkillManifest 详情 |

### Jobs API（`server/routers/jobs.py`）
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/jobs` | 提交执行（skill_id/engine/parameter/model/runtime_options） |
| GET | `/v1/jobs/{request_id}` | 查询状态 |
| GET | `/v1/jobs/{request_id}/result` | 获取最终结构化结果 |
| GET | `/v1/jobs/{request_id}/artifacts` | artifacts 列表 |
| GET | `/v1/jobs/{request_id}/bundle` | 下载 bundle zip |
| GET | `/v1/jobs/{request_id}/artifacts/{path}` | 下载单个产物 |
| GET | `/v1/jobs/{request_id}/logs` | stdout/stderr 全量快照 |
| GET | `/v1/jobs/{request_id}/events` | SSE 实时流（FCMP） |
| GET | `/v1/jobs/{request_id}/events/history` | 历史事件回放 |
| GET | `/v1/jobs/{request_id}/logs/range` | 日志区间读取 |
| GET | `/v1/jobs/{request_id}/interaction/pending` | 查询待决交互 |
| POST | `/v1/jobs/{request_id}/interaction/reply` | 提交交互回复 |
| POST | `/v1/jobs/{request_id}/upload` | 上传 input 文件 |
| POST | `/v1/jobs/{request_id}/cancel` | 取消运行 |
| POST | `/v1/jobs/cleanup` | 清理历史 runs 与 requests |

### Engines API（`server/routers/engines.py`）
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/v1/engines` | 引擎列表 |
| GET | `/v1/engines/{engine}/models` | 可用模型列表 |
| ...  | `/v1/engines/...` | 鉴权管理（OAuth 代理、CLI delegate、升级等）—— 路由较多，详见源码 |

### Skill Packages API（`server/routers/skill_packages.py`）
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/skill-packages/install` | 上传安装 skill 包 |
| GET | `/v1/skill-packages/{request_id}` | 安装状态查询 |

### Temp Skill Runs API（`server/routers/temp_skill_runs.py`）
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/temp-skill-runs` | 临时 skill 上传并创建 run |
| POST | `/v1/temp-skill-runs/{request_id}/upload` | 上传 skill 包并启动执行 |
| GET | `/v1/temp-skill-runs/{request_id}` | 查询状态 |
| GET | `/v1/temp-skill-runs/{request_id}/result` | 获取结果 |
| GET | `/v1/temp-skill-runs/{request_id}/artifacts` | artifacts 列表 |
| GET | `/v1/temp-skill-runs/{request_id}/bundle` | 下载 bundle |
| GET | `/v1/temp-skill-runs/{request_id}/artifacts/{path}` | 下载单个产物 |
| GET | `/v1/temp-skill-runs/{request_id}/logs` | 日志 |
| GET | `/v1/temp-skill-runs/{request_id}/events` | SSE 实时流 |
| GET | `/v1/temp-skill-runs/{request_id}/events/history` | 历史事件回放 |
| GET | `/v1/temp-skill-runs/{request_id}/logs/range` | 日志区间读取 |
| GET | `/v1/temp-skill-runs/{request_id}/interaction/pending` | 待决交互 |
| POST | `/v1/temp-skill-runs/{request_id}/interaction/reply` | 交互回复 |
| POST | `/v1/temp-skill-runs/{request_id}/cancel` | 取消 |

### UI Routes（`server/routers/ui.py`）
内建 Web UI，通过 Jinja2 模板渲染 HTML 页面。主要页面包括：
- `/ui` — 首页
- `/ui/skills/*` — Skill 管理（列表、详情）
- `/ui/runs/*` — Run 管理（列表、详情、日志）
- `/ui/engines/*` — 引擎管理（列表、模型、鉴权、升级）
- `/ui/skill-packages/*` — Skill 包安装
- `/ui/engines/auth/*` — 引擎鉴权会话管理（OAuth 代理、CLI delegate）
- `/ui/engines/tui/*` — Inline TUI 终端会话

#### `/v1/management/system/reset-data` 使用说明（高危）
- 该接口与 `scripts/reset_project_data.py` 共享同一重置核心逻辑。
- 必须提供确认文本：`RESET SKILL RUNNER DATA`。
- 支持 `dry_run` 预览模式（仅返回目标清单与统计，不执行删除）。
- 可选开关：
  - `include_logs`
  - `include_engine_catalog`
  - `include_agent_status`
  - `include_engine_auth_sessions`
- 默认会清理核心数据库、runs/requests 目录，以及 `data/ui_shell_sessions`。

### 请求/响应模型
Run 状态字段：
```json
{
  "request_id": "...",
  "status": "queued|running|waiting_user|succeeded|failed|canceled",
  "skill_id": "...",
  "engine": "...",
  "created_at": "...",
  "updated_at": "...",
  "pending_interaction_id": 12,
  "interaction_count": 3,
  "recovery_state": "none|recovered_waiting|failed_reconciled",
  "auto_decision_count": 0,
  "warnings": [],
  "error": null
}
```

错误响应规范：
```json
{
  "error": {
    "code": "SCHEMA_VALIDATION_FAILED|ENGINE_FAILED|TIMEOUT|CANCELED_BY_USER|SKILL_NOT_FOUND|SKILL_ENGINE_UNSUPPORTED|SESSION_RESUME_FAILED|INTERACTIVE_MAX_ATTEMPT_EXCEEDED|ORCHESTRATOR_RESTART_INTERRUPTED|...",
    "message": "...",
    "details": {},
    "request_id": "..."
  }
}
```

================================================================================
10. 技术栈
================================================================================
| 类别 | 技术 |
|------|------|
| 语言 | Python 3.11+ |
| 框架 | FastAPI + Uvicorn |
| 数据校验 | Pydantic v2（请求/响应模型） + jsonschema（输出校验） |
| 模板引擎 | Jinja2（prompt 渲染 + UI 模板） |
| 配置系统 | yacs（`server/core_config.py`：结构化默认值） + 环境变量覆盖 |
| 进程管理 | asyncio（`create_subprocess_exec`） + 超时/取消控制 |
| 存储 | 文件系统（workspace） + SQLite（`RunStore` run 状态） |
| 容器化 | Docker / docker-compose；详见 `docs/containerization.md` |

容器化说明：
- 镜像仅提供运行时，不打包 agent CLI。
- CLI 配置通过 `SKILL_RUNNER_AGENT_HOME` 环境变量隔离，通过 volume 持久化。
- 数据目录容器内默认 `/data`，主机端通过 `SKILL_RUNNER_DATA_DIR` 覆盖。

================================================================================
11. 安全/权限/资源限制
================================================================================
- 默认仅绑定 `127.0.0.1`。
- **OAuth 鉴权**：各引擎通过 OAuth 代理或 CLI delegate 完成 token 获取与刷新（`server/runtime/auth/`）。
- **Trust Folder 管理**：`server/services/orchestration/` 中实现 trust folder 策略注册与生命周期管理，平衡安全与易用性。
- **Inline TUI Profile**：部分引擎通过 inline TUI 终端会话执行鉴权，使用 minimal-permission profile 限制 shell 工具权限。
- 每个 run 有 timeout（通过 `SKILL_RUNNER_ENGINE_HARD_TIMEOUT_SECONDS` 配置，默认 1200 秒）。
- 并发限制（`ConcurrencyManager`）。
- 子进程环境变量最小化（agent 隔离 HOME：`SKILL_RUNNER_AGENT_HOME`）。
- 审计日志：所有 attempt 的 stdout/stderr/events/fs-diff 持久化到 `.audit/`。

================================================================================
12. 版本演进简史
================================================================================
| 版本 | 里程碑 |
|------|--------|
| v0 | 项目骨架 + FastAPI + Codex 引擎端到端 |
| v0.2 | Gemini 引擎 + Skill 安装/临时执行 + 基础 UI |
| v0.3 | iFlow + OpenCode 引擎 + interactive 会话 + FCMP 事件协议 + OAuth 鉴权 + Session 状态机 + 可观测性 + Skill Patcher + inline TUI + Management API |

================================================================================
13. 示例 Skill（测试用 fixtures）
================================================================================
当前 `tests/fixtures/skills/` 中包含以下 fixture skills：

| Skill | 用途 |
|-------|------|
| `demo-prime-number` | 基础自动化 skill：质数判定 |
| `demo-bible-verse` | 文本生成类 skill |
| `demo-auto-skill` | 自动模式参考实现 |
| `demo-interactive-skill` | 多轮交互模式参考实现 |
| `demo-pandas-stats` | 数据分析类 skill |
| `demo-bad-input` | 错误处理测试：非法输入 |
| `demo-bad-output` | 错误处理测试：非法输出 |
| `demo-missing-artifacts` | 错误处理测试：缺失产物 |
| `demo-missing-result` | 错误处理测试：缺失结果 |

================================================================================
14. 环境变量参考
================================================================================
| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SKILL_RUNNER_DATA_DIR` | 数据目录（runs/requests/logs） | `<project>/data`（容器内 `/data`） |
| `SKILL_RUNNER_AGENT_CACHE_DIR` | Agent CLI 缓存根目录 | 平台相关（容器内 `/opt/cache/skill-runner`） |
| `SKILL_RUNNER_AGENT_HOME` | Agent 隔离 HOME 目录 | `<cache_dir>/agent-home` |
| `SKILL_RUNNER_NPM_PREFIX` | 引擎 CLI 的 npm 安装前缀 | 自动检测 |
| `SKILL_RUNNER_ENGINE_HARD_TIMEOUT_SECONDS` | 引擎执行硬超时 | `1200` |
| `SKILL_RUNNER_SESSION_TIMEOUT_SEC` | 会话超时 | `1200` |
| `ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED` | 是否持久化写入 `data/engine_auth_sessions`（调试用途） | `false` |
| `LOG_DIR` | 全局应用日志目录 | `data/logs` |
| `LOG_FILE_BASENAME` | 全局日志文件名 | `skill_runner.log` |
| `LOG_ROTATION_WHEN` | 日志按时轮换策略 | `midnight` |
| `LOG_ROTATION_INTERVAL` | 日志轮换间隔 | `1` |

================================================================================
15. 日志配置 (Logging)
================================================================================
日志由 `server/logging_config.py` 配置。默认输出到终端与 `data/logs/`，并按天轮换。

日志配置分为两部分：

- Settings 页面可写并持久化到 `data/system_settings.json`：
  - `logging.level`
  - `logging.format`
  - `logging.retention_days`
  - `logging.dir_max_bytes`
- 系统配置/环境变量输入（Settings 页面只读展示）：
  - `LOG_DIR`
  - `LOG_FILE_BASENAME`
  - `LOG_ROTATION_WHEN`
  - `LOG_ROTATION_INTERVAL`

当目录总大小超过 `logging.dir_max_bytes` 时，系统会自动淘汰最旧归档日志文件（不会删除当前活动日志文件）。

管理 UI 中：

- `/ui` 首页提供 Settings 导航入口
- `/ui/settings` 承载日志设置与 data reset 危险操作区

`/v1/management/system/reset-data` 仍保持原确认文本保护；当 `ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED=false` 时，Settings 页面不会显示 engine auth session 清理项。
