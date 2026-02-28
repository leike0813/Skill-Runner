# Agent Skill Runner（REST）开发文档（给 Codex 用）
Version: v0.2.0
目标读者：Codex（开发协作者）+ 项目开发者
用途：为“从0实现一个服务化封装成熟CLI Agent工具的 Skill Runner”提供统一的顶层设计、约束、接口、数据结构、里程碑与待决问题。Codex 将基于本文档继续与用户敲定细节并落地实现。

================================================================================
0. 项目一句话定义
================================================================================
实现一个本地/自托管的 REST 服务（Agent Skill Runner），用于以统一 API 方式调用成熟商用/社区 CLI agent 工具（优先 Codex，其后 Gemini CLI、iFlow CLI）执行“完全自动化 skill”，并返回严格结构化的结果（满足 output schema）与产物（artifacts）。Runner 仅负责执行编排、输出校验与必要的规范化（normalization）链，不为 skill 的业务正确性背书。

================================================================================
1. 核心需求（必须实现）
================================================================================
R1. REST API 暴露
- 外部通过 REST API 调用某个 skill（skill 已经封装了自动化任务逻辑）；
- API 支持同步（短任务）与异步（长任务）两种模式（至少异步要有）。

R2. Skill 可插拔
- skills 以“插件/包”的形式加载（本地目录扫描或注册表）；
- skill 必须提供 input_schema 和 output_schema（JSON Schema）；
- skill 必须声明其 artifacts 合同（至少角色 role / 生成位置 / mime / 必需与否）。

R3. 多引擎支持（分阶段）
- v0：仅 codex 引擎（Codex CLI）跑通端到端
- v0.2：加入 gemini
- v0.3：加入 iflow
要求：Runner 内部定义统一 EngineAdapter 接口，将不同 CLI 的调用方式与输出解析差异封装起来。

R4. 输出稳定性：验证 + 规范化
- Runner 在返回前必须验证 skill 的输出 JSON 是否满足 output_schema；
- 若不合法，Runner 进入规范化链：
  - 优先 deterministic 解析/修复（去 code fence、抽取 JSON 等）
  - 可调用 skill 自带 normalizer（可选）
  - 可调用 skill 自带 fallback（可选；不依赖 LLM）
  - 最后可启用 Runner 内建的“repair/normalize”逻辑（可以是程序或内建 skill；是否使用 LLM 由配置控制）
- 若规范化后仍不合法：返回结构化错误响应
- 任何规范化/降级必须在响应中附带明确警示（warnings），并保留原始输出供审计。

R5. Artifacts 一等公民
- skill 执行产生的文件产物必须在 workspace 中被收集、索引（manifest），并通过 API 可下载或可定位到宿主路径；
- 响应中必须列出 artifacts（role/mime/sha256/size/url或host_path）。

R6. 自动化与非交互
- skill 必须可完全自动化：执行过程中不得等待人工交互；
- Runner 要能强制超时、取消（kill 子进程）；
- Runner 要记录日志与事件（至少 stdout/stderr；推荐 JSONL events）。

================================================================================
2. 非目标（明确不做）
================================================================================
N1. 不实现“自定义模型/自建agent平台”（不像 OpenHands 这类产品）
N2. 不保证 skill 的业务正确性，只保证执行与结构化输出合同
N3. 不做复杂权限系统（v0 仅本机使用；可加 token 简单鉴权）
N4. 不实现分布式队列/多节点（v0 单机即可）

================================================================================
3. 总体架构（建议实现）
================================================================================
组件：
A) API Server：FastAPI（推荐）或 Node/Express（均可；v0 推荐 FastAPI + Pydantic）
B) Job Orchestrator：管理 run 状态、并发、超时、取消；将 run 作为异步任务执行
C) Skill Registry：扫描 skills 目录，读取 manifest，校验 schema，提供技能元数据查询
D) Engine Adapters：
   - CodexAdapter（v0）
   - GeminiAdapter（v0.2）
   - IFlowAdapter（v0.3）
E) Workspace Manager：每次 run 创建隔离目录，保存 input/result/logs/artifacts/manifest
F) Output Validator：JSON Schema 校验 output；不通过进入 normalization pipeline
G) Normalization Pipeline：deterministic + skill-provided + runner-provided
H) Artifact Manager：生成 manifest.json，计算 sha256/size/mime，提供下载

================================================================================
4. 工作区（Workspace）约定（强推荐）
================================================================================
每个 run 一个目录：
/data/runs/<run_id>/
  skill.json                 # 运行时skill元信息快照（id/version/engine）
  input.json                 # 输入payload（已通过 input_schema 校验）
  logs/
    stdout.txt
    stderr.txt
    events.jsonl             # 可选：逐条事件（结构化）
  artifacts/                 # skill 的所有文件产物必须放这里（默认）
  raw/
    engine_output.txt        # 引擎原始输出（尽量保存）
    engine_output.json       # 若引擎有 envelope json
  result/
    result.json              # 最终对外结果（保证满足 output_schema）
    validation.json          # 校验/规范化记录（warnings/errors/steps）
  manifest.json              # artifacts 索引（role/path/mime/sha256/size）

运行时写入策略：
- skill 仅可写 artifacts/ 与 result/（按配置限制；v0可放宽但要记录）
- runner 永远写 logs/ raw/ result/ manifest.json

================================================================================
5. Skill 包结构与规范（基于 Agent Skills 官方规范重新起草）
================================================================================
【目标】
- 与 Agent Skills 标准兼容：任何 skills-compatible agent 至少能发现并读取 SKILL.md 的 name/description，并在激活时加载其正文指令。:contentReference[oaicite:0]{index=0}
- 在此基础上，Runner 进一步“收紧约束”为可全自动化的 AutoSkill Profile：要求提供 input/output schema、artifacts 合同、（可选）normalizer/fallback 等，用于 REST 自动化执行与稳定结构化返回。

------------------------------------------------------------------------------
5.1 标准要求（Agent Skills Spec 的硬约束）
------------------------------------------------------------------------------
一个 skill 是一个目录，至少包含一个 SKILL.md：:contentReference[oaicite:1]{index=1}

  skill-name/
  └── SKILL.md          # 必需

SKILL.md 的格式：
- 必须包含 YAML frontmatter + Markdown 正文指令。:contentReference[oaicite:2]{index=2}
- frontmatter 必需字段：
  - name：1-64 字符，小写字母/数字/连字符（-），不能以 - 开头/结尾、不能有连续 --，并且必须与父目录名一致。:contentReference[oaicite:3]{index=3}
  - description：1-1024 字符，描述“做什么 + 什么时候用”。:contentReference[oaicite:4]{index=4}
- frontmatter 可选字段（标准层）：
  - license
  - compatibility（用于声明环境需求）
  - metadata（标准定义为 string->string 的额外键值映射）
  - allowed-tools（实验性，支持不保证）:contentReference[oaicite:5]{index=5}

可选目录（标准推荐）：
- scripts/：可执行代码（python/bash/js 等，具体取决于 agent 实现）:contentReference[oaicite:6]{index=6}
- references/：补充文档（按需加载）:contentReference[oaicite:7]{index=7}
- assets/：静态资源（模板、图片、数据文件等）:contentReference[oaicite:8]{index=8}

文件引用与组织建议（标准推荐）：
- SKILL.md 内引用同目录下文件时使用相对路径；
- 建议“引用链”不要太深，最好只在 SKILL.md 下一级引用。:contentReference[oaicite:9]{index=9}

------------------------------------------------------------------------------
5.2 Runner 的“AutoSkill Profile”收紧约束（在标准之上扩展）
------------------------------------------------------------------------------
【原则】
- 保持 SKILL.md 的标准字段最小化且通用（name/description/compatibility 等）。
- Runner 所需的“自动化执行合同”（schemas、artifacts、entrypoint、fallback 等）不强行塞进标准 metadata（因为标准 metadata 是 string->string，嵌套结构不友好）。:contentReference[oaicite:10]{index=10}
- Runner 扩展信息放到 skill 目录内的额外文件中（不会破坏标准兼容性）。

【推荐目录结构（Runner 约定）】
  skill-name/
  ├── SKILL.md                         # 必需：标准 frontmatter + 指令正文
  ├── assets/                          # 推荐：Runner 扩展静态资源（标准允许）:contentReference[oaicite:11]{index=11}
  │   ├── runner.json                  # 必需（Runner 约定）：AutoSkill Manifest（见 5.3）
  │   ├── input.schema.json            # 必需（Runner 约定）：文件输入 JSON Schema
  │   ├── parameter.schema.json        # 必需（Runner 约定）：参数 JSON Schema
  │   ├── output.schema.json           # 必需（Runner 约定）：输出 JSON Schema
  │   ├── gemini_settings.json         # 可选：Gemini CLI 推荐配置（遵循 CLI Schema）
  │   ├── iflow_settings.json          # 可选：iFlow CLI 推荐配置
  │   ├── codex_config.toml            # 可选：Codex CLI 推荐配置
  │   └── ...                          # 其他模板/数据文件
  ├── scripts/                         # 可选：可执行脚本（标准允许）:contentReference[oaicite:12]{index=12}
  │   ├── normalize.py                 # 可选：非 LLM 规范化器（输出合规 JSON）
  │   ├── fallback.py                  # 可选：非 LLM fallback（输出合规 JSON）
  │   └── ...                          # 其他工具脚本
  └── references/                      # 可选：参考文档（标准允许）:contentReference[oaicite:13]{index=13}
      └── REFERENCE.md

【Runner 对 skill 的强约束（AutoSkill Profile）】
- 必须声明执行模式：`execution_modes`（至少包含 `auto`；若支持交互再显式加入 `interactive`）。
- 必须提供：
  - assets/input.schema.json
  - assets/parameter.schema.json
  - assets/output.schema.json
  - assets/runner.json（AutoSkill Manifest）
- 必须声明 artifacts 合同（在 runner.json 中），以便 Runner 能稳定地扫描/索引/返回产物。

------------------------------------------------------------------------------
5.3 AutoSkill Manifest（assets/runner.json）（Runner 约定）
------------------------------------------------------------------------------
该文件是 Runner 的执行合同（与标准分离），用于让 Runner 以 REST 自动化方式调用 skill 并返回稳定结构。

建议字段（v0 最小集合）：
{
  "id": "skill-name",                 // 必须等于 SKILL.md frontmatter.name 且等于目录名（标准要求 name 匹配目录）:contentReference[oaicite:14]{index=14}
  "version": "1.0.0",
  "engines": ["codex", "gemini", "iflow", "opencode"], // 可选：显式允许的引擎集合
  "unsupported_engines": ["iflow"],        // 可选：显式不支持的引擎集合
  "execution_modes": ["auto", "interactive"], // 必填：允许的执行模式（仅 auto|interactive）
  "entrypoint": {
    "type": "prompt|script|hybrid",
    "prompt": {
      "template": "assets/prompt.txt", // 可选：prompt 模板路径（相对 skill 根）
      "result_mode": "file|stdout",    // file: 写 result.json；stdout: 打印 JSON
      "result_file": "result/result.json"
    },
    "script": {
      "command": "python scripts/run.py"
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
  "normalizer": {
    "command": "python scripts/normalize.py",
    "enabled": true
  },
  "fallback": {
    "command": "python scripts/fallback.py",
    "enabled": false
  }
}

说明：
- runner.json 是 Runner 私有合同：不会影响标准 skills-compatible agent 读取 SKILL.md。
- `engines` 为可选字段；缺失时默认按“系统支持的全部引擎”处理。
- `unsupported_engines` 为可选字段；用于从允许集合中剔除不支持的引擎。
- 若同时声明 `engines` 与 `unsupported_engines`，两者不允许有重复项；计算后的有效集合必须非空。
- `input.schema.json` / `parameter.schema.json` / `output.schema.json` 在上传阶段会执行服务端 meta-schema 预检，确保 Runner 关键扩展字段合法（如 `x-input-source`、`x-type`）。
- `execution_modes` 必须为非空数组，值仅允许 `auto` / `interactive`。新上传或更新包缺失该字段会被拒绝；存量已安装且缺失的 skill 在兼容期按 `["auto"]` 解释并记录 deprecation 警告。
- `max_attempt` 为可选正整数（`>=1`），仅作用于 `interactive`：
  - 当 `attempt_number >= max_attempt` 且当轮既无 `__SKILL_DONE__` 也未通过 output schema 软完成时，run 失败并返回 `INTERACTIVE_MAX_ATTEMPT_EXCEEDED`。
- entrypoint.type=prompt 时，SKILL.md 正文仍应写清“执行步骤/输出格式/产物位置”，以便引擎（如 Codex）在激活 skill 时能按指令生成结果；同时 Runner 以 runner.json 作为“机器可执行合同”来编排与校验。
- entrypoint.type=script/hybrid 时，scripts/ 中的脚本作为更确定的执行路径（建议用于 normalize/fallback 或关键产物生成）。

------------------------------------------------------------------------------
5.4 SKILL.md 写法建议（兼顾标准与 Runner 自动化）
------------------------------------------------------------------------------
SKILL.md frontmatter（标准最小）：
---
name: skill-name
description: 清晰描述“做什么 + 什么时候用”，包含关键词以便检索/匹配。:contentReference[oaicite:15]{index=15}
compatibility: 可选，写明需要的环境/依赖/网络等（若确有要求）。:contentReference[oaicite:16]{index=16}
---

正文（对引擎友好）建议包含：
- When to use / Inputs / Outputs / Artifacts
- 明确：最终结构化输出必须符合 output.schema.json（并指向相对路径 assets/output.schema.json）
- 若结果写文件：明确写入位置（例如 result/result.json）与产物位置（artifacts/ 下）
- 引用脚本/资源时，使用相对路径；尽量保持引用层级浅。:contentReference[oaicite:17]{index=17}

================================================================================
6. 引擎适配（EngineAdapter）统一接口（内部）
================================================================================
定义一个统一执行契约：

EngineAdapter.run(
  skill_manifest,
  input_json,
  workspace_paths,
  options
) -> EngineRunResult

配置加载逻辑（Config Loading）：
1. 加载 Engine Default（`server/assets/configs/<engine>/default.*`，最低优先级）
2. 加载 Skill Recommended Config（从 `assets/<engine>_config.*` 或 `assets/<engine>_settings.json`）
3. 加载 User Options（API 调用参数：`model` + `runtime_options` + `<engine>_config`）
4. 加载 Enforced Config（`server/assets/configs/<engine>/enforced.*`，最高优先级）
5. Merge & Validate（遵循 CLI 官方 Schema）
6. 写入运行时配置：
   - Codex：更新全局 `~/.codex/config.toml` 的 profile；
   - Gemini / iFlow：写入 `run_dir/.<engine>/settings.json`；
   - OpenCode：写入 `run_dir/opencode.json`，并按模式覆盖 `permission.question`（`auto=deny`，`interactive=allow`）。

EngineRunResult 字段建议：
- exit_code: int
- raw_stdout: str
- raw_stderr: str
- envelope_json: dict|null        # 若有（部分 CLI 可能输出结构化 envelope）
- parsed_json: dict|null          # runner 尝试从输出中解析出的 JSON
- output_file_path: str|null      # 若引擎直接写 result.json
- artifacts_created: [str]        # 初步扫描得到的产物相对路径列表
- events: [dict] or events.jsonl  # 可选

Interactive 会话恢复约定（v0.3）：
- 统一为单一可恢复会话范式（single resumable），不再区分 `resumable/sticky_process` 双档位。
- Orchestrator 在 interactive 首回合前完成恢复能力探测；无论 probe 结果如何，都走统一可恢复路径并持久化 `EngineSessionHandle`。
- 自动回复开关：`runtime_options.interactive_auto_reply`（默认 `false`）：
  - `false`：保持人工回复门禁；`waiting_user` 超时后不自动继续。
  - `true`：等待超时触发自动决策并继续执行（统一回到 `queued` 再恢复）。
- interactive 完成判定（双轨）：
  - 强条件：在 assistant 回复内容中检测到 `__SKILL_DONE__`。
  - 软条件：未检测到 marker，但当轮输出通过 output schema。
  - 软条件完成会记录 warning：`INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER`。
  - `tool_use`/tool 回显中的 marker 文本不参与完成判定。
  - ask_user 提示建议采用 YAML（非 JSON）并包裹 `<ASK_USER_YAML>...</ASK_USER_YAML>`，降低与业务输出 JSON 混淆风险。
  - ask_user 提示仅用于 pending/UI enrichment，不参与生命周期门控判定。
- 服务启动期恢复（startup reconciliation）：
  - 扫描非终态 run：`queued/running/waiting_user`。
  - `waiting_user`：校验 `pending_interaction_id + session handle`，有效则保持 waiting；无效则 `SESSION_RESUME_FAILED`。
  - `queued/running`：默认收敛为 `failed`，错误码 `ORCHESTRATOR_RESTART_INTERRUPTED`。
  - 清理逻辑要求幂等，不依赖 sticky 专属进程绑定语义。
- 恢复观测字段：
  - `recovery_state`: `none | recovered_waiting | failed_reconciled`
  - `recovered_at`: 恢复决策写入时间（ISO）
  - `recovery_reason`: 恢复或失败收敛原因（用于运维排障）
- 三引擎句柄来源：
  - Codex: `exec --json` 首条 `thread.started.thread_id`
  - Gemini: JSON 返回体 `session_id`
  - iFlow: `<Execution Info>` 中 `session-id`
- 标准错误码：
  - `SESSION_RESUME_FAILED`
  - `INTERACTIVE_MAX_ATTEMPT_EXCEEDED`
  - `ORCHESTRATOR_RESTART_INTERRUPTED`

CodexAdapter(v0) 策略（建议）：
- 使用 codex 的非交互模式执行；
- 优先让 skill 通过约定在 workspace/result/result.json 写出最终 JSON；
- 或让 codex 在 stdout 输出 JSON，再由 runner 捕获；
- 若 codex 支持 schema 输出能力（如 output schema），应尽量使用以减少不合法输出概率；
- 支持 --json 事件流时将其写入 events.jsonl（可选，v0不强制）。

GeminiAdapter(v0.2) 策略（建议）：
- **Skill Installation**: Copy entire skill directory to `workspace/.gemini/skills/<skill_id>`.
- **Configuration**: Ensure `experimental.skills=true` in `settings.json`.
- **Invocation**: Use an "Invocation Prompt" (defined in `runner.json` or default) to tell the agent to use the skill.
      Example: "Please call the skill named <skill-name>, with <parameters> to execute on <input_filepath>".
- **Execution**: `gemini --yolo "{invocation_prompt}"`.
- **Result**: Agent natively executes skill steps (finding assets/scripts relative to itself) and outputs result.

IFlowAdapter(v0.3) 策略（待定）：
- 调研 iFlow CLI 非交互调用方式与输出模式；
- 至少能获取 stdout/stderr；若支持 JSON 输出则优先；
- 不支持时沿用 runner 的解析/规范化链。

================================================================================
7. 输出校验与规范化链（核心逻辑）
================================================================================
步骤：
S1. 解析阶段（parse）
- 优先读取 workspace/result/result.json（若存在）
- 否则尝试从引擎 envelope_json / stdout 中提取 JSON：
  - 提取第一个合法 JSON 对象/数组
  - 去除 ```json code fence``` 包裹
  - 严格限制解析修复范围（禁止“猜测字段含义”）

S2. 校验阶段（validate）
- 用 output.schema.json 对 parsed_json 校验
- 若通过：进入 artifacts 索引阶段
- 若失败：进入规范化链（normalize）

S3. 规范化链（normalize pipeline）
N0 Deterministic Normalize（runner 内置）
- 去 fence、trim、修复常见格式问题（仅语法层）
- 再次 schema validate
N1 Skill Normalizer（可选）
- 若 runner.json 声明 normalizer.command：执行该脚本
- 该脚本输入：raw 输出文件路径 + schema 路径 + workspace
- 输出：workspace/result/result.json
- 校验
N2 Skill Fallback（可选，非LLM）
- 若声明 fallback.command：执行 fallback
- 输出：workspace/result/result.json
- 校验
N3 Runner Repair（可选，默认关闭或可配置）
- 可用内建程序/内建 skill 将 raw 输出“修复成 schema 合规 JSON”
- 必须附带 warnings 标明：normalization_level = N3、可能引入语义偏差

S4. 最终失败（error）
- 若仍不合规：返回结构化错误响应
- 必须返回：validation_errors、raw_output_path、建议排查信息

响应必须包含 warnings（如发生规范化/降级）：
- warnings[]: {code, message, level, normalization_level, details}

================================================================================
8. Artifacts 管理与返回
================================================================================
Artifact 索引规则：
- 依据 runner.json artifacts 合同扫描 workspace/artifacts/
- 对每个匹配文件计算：
  - sha256
  - size
  - mime（可用 python-magic 或简单后缀映射，v0可先后缀映射）
- 生成 manifest.json：
  artifacts: [
    {role, path_rel, filename, mime, size, sha256, required}
  ]

返回给客户端：
- 通过单次请求下载 bundle：
  GET /v1/jobs/{request_id}/bundle

================================================================================
9. REST API 设计（v1）
================================================================================
基础：
- Base URL: http://127.0.0.1:<port>/v1
- 所有请求/响应 JSON，UTF-8
- 响应按接口各自的 Response Model 返回（见 API Reference）

分层约定（Domain API vs UI Adapter）：
- Domain API（推荐）：`/v1/management/*`，面向任意前端，返回稳定 JSON 语义。
- Execution API（兼容）：`/v1/jobs*`、`/v1/temp-skill-runs*`、`/v1/skills*`、`/v1/engines*`，保留执行链路与历史契约。
- UI Adapter：`/ui/*` 只负责页面渲染与交互，不引入仅 UI 可见的私有业务字段。
- 外部前端优先对接 Domain API；内建 UI 必须同步遵循同一契约，不得定义分叉语义。
- 新增管理页能力优先落在 Domain API，再由 `/ui/*` 复用该语义。

Management API（推荐前端入口）：
1) GET /v1/management/skills
- 返回 `SkillSummary` 列表（`id/name/version/engines/unsupported_engines/effective_engines/health`）

2) GET /v1/management/skills/{skill_id}
- 返回 `SkillDetail`（补充 `schemas/entrypoints/files/execution_modes`）

3) GET /v1/management/skills/{skill_id}/schemas
- 返回 `input/parameter/output` schema 内容（用于动态表单渲染与前置校验）

4) GET /v1/management/engines
- 返回 `EngineSummary` 列表（`engine/cli_version/auth_ready/sandbox_status/models_count`）

5) GET /v1/management/engines/{engine}
- 返回 `EngineDetail`（补充 `models/upgrade_status/last_error`）

6) GET /v1/management/runs/{request_id}
- 返回 `RunConversationState`（包含 `pending_interaction_id`、`interaction_count`、`auto_decision_count`、`last_auto_decision_at`、`recovery_state`、`recovered_at`、`recovery_reason`、`poll_logs`）

7) GET /v1/management/runs/{request_id}/files
- 返回对话窗口文件树

8) GET /v1/management/runs/{request_id}/file?path=...
- 返回文件预览（带路径越界保护）

9) GET /v1/management/runs/{request_id}/events
- SSE 实时流（FCMP 单流：`snapshot/chat_event/heartbeat`）

9a) GET /v1/management/runs/{request_id}/events/history
- 结构化历史事件回放（支持 `from_seq/to_seq/from_ts/to_ts`）

9b) GET /v1/management/runs/{request_id}/logs/range
- 日志区间读取（`stream=stdout|stderr|pty` + `byte_from/byte_to`），供 `raw_ref` 回跳

10) GET /v1/management/runs/{request_id}/pending
- 查询当前待决交互

11) POST /v1/management/runs/{request_id}/reply
- 提交交互回复（语义与 jobs 保持一致）

12) POST /v1/management/runs/{request_id}/cancel
- 取消运行（语义与 jobs 保持一致）

内建 UI Run 详情页布局约定：
- 文件树区与文件预览区使用固定最大高度并在各自容器内滚动，避免长内容拉伸整页。
- stdout 作为主对话窗口；用户 reply 输入区固定在主对话窗口下方并按 pending 状态启用。
- stderr 以独立窗口展示，与 stdout 主对话区分离。

内建 E2E 示例客户端（独立服务）：
- 服务入口：`e2e_client/app.py`，默认端口 `8011`，通过 `SKILL_RUNNER_E2E_CLIENT_PORT` 覆盖，无效值回退 `8011`。
- 后端地址：`SKILL_RUNNER_E2E_CLIENT_BACKEND_BASE_URL`（默认 `http://127.0.0.1:8000`）。
- 客户端仅通过 HTTP API 与后端通信，不依赖 `server` 内部模块。
- 执行页从 skill detail 的 `execution_modes` 读取允许模式，用户可选择后写入 `runtime_options.execution_mode`。
- 执行页支持 model 选择（按 engine 动态加载）与常用 runtime_options 配置并一并提交。
- 录制回放：关键动作（create/upload/reply/result_read）写入 `e2e_client/recordings/*.json`，回放页支持单步播放。

旧 UI 数据接口弃用策略（Web 客户端迁移后）：
- `warn`（默认）：旧接口继续返回，但附带 `Deprecation/Sunset/Link` 响应头，并记录调用日志。
- `gone`：旧接口直接返回 `410 Gone`。
- 环境变量：
  - `SKILL_RUNNER_UI_LEGACY_API_MODE=warn|gone`
  - `SKILL_RUNNER_UI_LEGACY_API_SUNSET`（默认 `2026-06-30`）

Endpoints：
1) GET /v1/skills
- 返回技能列表（id, version, name, description, engines）

2) GET /v1/skills/{skill_id}
- 返回 SkillManifest（包含 engines / schemas / artifacts / runtime 等）

3) POST /v1/jobs
Request:
{
  "skill_id": "demo-prime-number",
  "engine": "codex",
  "parameter": {                  # 对应 skill 的 parameter.schema.json
    "divisor": 10
  },
  "model": "gpt-5.2-codex@high",
  "runtime_options": {
    "debug": false,
    "interactive_reply_timeout_sec": 1200
  }
}
Response:
{
  "request_id": "...",
  "cache_hit": false,
  "status": "queued"
}

注：
- Input 文件（对应 input.schema.json）需通过 `POST /v1/jobs/{request_id}/upload` 单独上传。
- `engine` 必须在 skill 的有效引擎集合内（`effective_engines = (engines 或 全量支持引擎) - unsupported_engines`），否则返回 400（`SKILL_ENGINE_UNSUPPORTED`）。
- `model` 需从 `GET /v1/engines/{engine}/models` 中选择；Codex 使用 `name@reasoning_effort` 格式。
- interactive 会话超时统一使用 `runtime_options.interactive_reply_timeout_sec`（默认 1200 秒）。

4) GET /v1/jobs/{request_id}
- 查询状态与摘要
Response:
{
  "request_id": "...",
  "status": "queued|running|waiting_user|succeeded|failed|canceled",
  "skill_id": "...",
  "engine": "...",
  "created_at": "...",
  "updated_at": "...",
  "pending_interaction_id": 12 | null,
  "interaction_count": 3,
  "recovery_state": "none|recovered_waiting|failed_reconciled",
  "recovered_at": "2026-02-16T00:05:00Z | null",
  "recovery_reason": "resumable_waiting_preserved|session_handle_invalid|orchestrator_restart_interrupted|...|null",
  "auto_decision_count": 0,
  "last_auto_decision_at": null,
  "warnings": [...],
  "error": {...} | null
}

注：
- `waiting_user` 为非终态；若 `pending_interaction_id` 非空，客户端应优先走 pending/reply，而非继续轮询日志。
- 当 `recovery_state=failed_reconciled` 时，优先结合 `error.code` 与 `recovery_reason` 判定重启影响。

5) GET /v1/jobs/{request_id}/result
- 返回最终结构化结果（必须满足 output_schema）
Response:
{
  "request_id": "...",
  "result": {
    "status": "succeeded|failed",
    "data": {...} | null,
    "artifacts": [...],
    "validation_warnings": [...],
    "error": {...} | null
  }
}

6) GET /v1/jobs/{request_id}/artifacts
- 返回 artifacts 列表（相对路径）

7) GET /v1/jobs/{request_id}/bundle
- 下载 bundle zip（包含 manifest.json 与产物文件）

8) GET /v1/jobs/{request_id}/logs
- 返回 prompt/stdout/stderr 的全量快照（适合低频排查）

9) GET /v1/jobs/{request_id}/events
- 返回 `text/event-stream` FCMP 单流（适合实时监控与断线续传）
- query: `cursor`（基于 `chat_event.seq`）
- 事件: `snapshot/chat_event/heartbeat`
- `waiting_user` 为非终态，推荐改走 pending/reply 流程。

9c) GET /v1/jobs/{request_id}/events/history
- 返回 FCMP 历史事件，支持按 `seq` 与时间区间拉取。

9d) GET /v1/jobs/{request_id}/logs/range
- 返回日志字节区间，用于前端从 `raw_ref` 回跳原始证据。

9a) GET /v1/jobs/{request_id}/interaction/pending
- 读取当前待决交互问题；仅 `runtime_options.execution_mode=interactive` 可用。

9b) POST /v1/jobs/{request_id}/interaction/reply
- 提交交互回复；仅 `runtime_options.execution_mode=interactive` 可用。
- 当请求为非 interactive 时，返回 `400`（而非按 run 状态推断）。

10) POST /v1/jobs/{request_id}/cancel
- 主动终止活跃 run（`queued/running/waiting_user`）
- 终态幂等：若已是 `succeeded/failed/canceled`，返回 `accepted=false`
- 成功取消后统一落 `status=canceled` 且 `error.code=CANCELED_BY_USER`

11) POST /v1/jobs/cleanup
- 清理 runs.db 以及 data/runs 与 data/requests 中的历史记录

错误响应规范（统一）：
{
  "error": {
    "code": "SCHEMA_VALIDATION_FAILED|ENGINE_FAILED|TIMEOUT|CANCELED|SKILL_NOT_FOUND|...",
    "message": "...",
    "details": {...},
    "request_id": "..."
  }
}

================================================================================
10. 技术栈建议（v0推荐）
================================================================================
语言：Python 3.11+
框架：FastAPI + Uvicorn
校验：Pydantic v2（输入payload） + jsonschema（输出校验）或 pydantic + generated models（二选一）
进程管理：asyncio.create_subprocess_exec + 超时/取消控制
存储：文件系统（workspace）；run 状态可用 sqlite（可选）或简单 JSON 状态文件（v0）
配置：YAML + 环境变量（端口、runs目录、并发、默认超时、repair开关）

Docker：
- v0 可先不 Docker；但结构要支持容器化（runs目录可挂载）
- 若做 Docker：提供 docker-compose.yml + volumes（/data/runs, /skills）

容器化说明：
- 参考 `docs/containerization.md`，镜像仅提供运行时，不打包 agent CLI。
- CLI 配置默认在用户 HOME（容器内 `/root`），并通过 volume 持久化。

================================================================================
11. 安全/权限/资源限制（v0最低要求）
================================================================================
- 默认仅绑定 127.0.0.1
- 允许简单 token（可选）
- 每个 run 都有 timeout
- 并发限制（max_running_jobs）
- 子进程环境变量最小化（只传必要：API keys 等，但建议由服务端配置，不由客户端传）
- 记录审计：raw 输出、校验错误、规范化步骤

================================================================================
12. 里程碑计划（建议）
================================================================================
M0 (Day 0-1): 项目骨架
- FastAPI 起服务
- skills 目录扫描 + /skills endpoints
- workspace 管理 + run_id（内部）

M1 (Day 2-3): Codex 引擎端到端
- CodexAdapter 能非交互运行一个 demo skill
- /v1/jobs 提交 -> 生成 result.json -> /v1/jobs/{id}/result 返回
- stdout/stderr 记录

M2 (Day 3-4): 校验 + 规范化链 N0
- input_schema 校验（请求时）
- output_schema 校验（返回前）
- deterministic normalize（去 fence、提取 JSON）
- warnings 机制

M3 (Day 4-5): Artifacts 管理
- artifacts 扫描 + sha256 + manifest.json
- /artifacts 列表与下载

M4 (v0.2): gemini adapter
M5 (v0.3): iflow adapter + 规范化链 N1/N2（skill normalizer/fallback）

================================================================================
13. 示例 Skill（用于开发自测）
================================================================================
建议创建一个最简单 demo：
skill_id: "demo.echo"
输入：{ "text": string }
输出：{ "text": string, "length": int, "normalized": bool, "warnings": [string] }
artifacts：可选生成 notes.md

再创建一个贴近 Zotero 的 demo：
skill_id: "zotero.parse_attachment"
输入：{ "attachment_path": string, "item_key": string, "output_format": "json|md" }
输出：{ "title": string, "summary": string, "tags": [string], "attachments": [ { "role": string, "filename": string } ] }
artifacts：parsed.json, notes.md

================================================================================
14. 待决问题（需要 Codex 与用户一起敲定）
================================================================================
Q1. Skill 执行方式：prompt/script/hybrid 的最终形式？（建议 v0 先做 prompt/hybrid）
Q2. Codex CLI 的具体调用参数与安全策略：
- 是否要求 codex 使用只读/受限 sandbox？
- 是否统一强制在 workspace 内运行？
Q3. 规范化链 N3（Runner Repair）是否允许使用 LLM？
- 默认关闭？仅 debug 模式开启？需要显式配置？
Q4. API 响应中的 artifacts 返回 host_path 还是 url？
- Zotero 插件更适配哪种？（通常 url 更通用）
Q5. Job 状态存储：文件 vs sqlite
- v0 文件足够；v1 可能需要 sqlite 以便查询历史
Q6. iFlow CLI 的非交互能力与输出能力需要调研（命令/参数/是否支持 JSON）

================================================================================
15. 对 Codex 的工作指令（开始开发时）
================================================================================
- 请先生成项目目录结构与最小可运行 FastAPI skeleton
- 定义数据模型（RunCreateRequest/RunStatus/SkillManifest/ArtifactManifest/Warnings/ErrorResponse）
- 实现 Skill Registry：扫描 skills/*/assets/runner.json，加载 schemas 路径
- 实现 Workspace Manager：创建 run 目录、写 input.json、logs 目录
- 实现 Job Orchestrator：后台任务队列（async），支持取消与超时
- 实现 CodexAdapter：能运行 demo.echo（哪怕先用假命令/占位，也要接口对齐）
- 实现 Output Validator：jsonschema 校验 + deterministic normalize（N0）
- 实现 Artifact Manager：扫描 artifacts/ 并生成 manifest
- 实现 REST endpoints：/v1/skills, /v1/jobs, /v1/skill-packages, /v1/temp-skill-runs 及其查询/下载子路由
- 在每个阶段提交可运行的最小实现（MVP），并用 demo skill 自测

================================================================================
16. 日志配置 (Logging)
================================================================================
日志默认输出到终端与 `data/logs/`。可以通过环境变量控制：
- `LOG_LEVEL`: 日志级别（默认 `INFO`）
- `LOG_FILE`: 自定义日志文件路径（为空则使用默认文件）
- `LOG_MAX_BYTES`: 单个日志文件大小上限（默认 5MB）
- `LOG_BACKUP_COUNT`: 轮转备份文件数（默认 5）

示例：
```bash
LOG_LEVEL=DEBUG LOG_FILE=/tmp/skill_runner.log LOG_MAX_BYTES=1048576 LOG_BACKUP_COUNT=3 \
python server/main.py
```
