# CodeBuddy Code Engine 代码级接入计划

日期：2026-07-10  
OpenSpec change：add-codebuddy-code-engine  
调研依据：artifacts/codebuddy_engine_investigation_2026-07-10.md

## 0. 工件定位与维护规则

本文是代码级实施与 agent handoff 工件，展开代码结构、接口、数据流、失败矩阵、测试矩阵和阶段门禁。它不记录任务完成状态；唯一完成状态位于 openspec/changes/add-codebuddy-code-engine/tasks.md。

规范冲突时按以下优先级裁决：

1. 机器合同，包括 JSON Schema 和 invariants YAML。
2. OpenSpec delta specs。
3. OpenSpec design.md。
4. 本详细计划。
5. tasks.md 的验收摘要。

技术设计变化时，先修改机器合同或 specs/design，再同步本文。禁止仅修改 tasks 摘要形成新设计。

## 1. 调研证据与版本基线

### 1.1 已确认的产品能力

| 证据面 | 调研结论 | 接入影响 |
|---|---|---|
| CLI print mode | -p 可用于无交互执行 | 每个 attempt 使用 fresh subprocess |
| stream output | --output-format stream-json 产生 JSONL 事件 | 需要专属 framer/parser |
| session resume | -r 接受精确 session ID | waiting/reply 必须保存首个有效 session_id |
| structured output | --json-schema 配合 result.structured_output | 接入 shared structured-output pipeline |
| MCP | --mcp-config 与 --strict-mcp-config 可限制来源 | 每个 run 总是生成并传入受管配置 |
| project skills | .codebuddy/skills 可装载技能 | adapter profile 声明 workspace/subdir |
| settings | --settings 与 --setting-sources 可指定项目设置 | settings.json 由系统独占生成 |
| SDK auth | Python SDK authenticate 为 two-phase URL + wait | SDK 仅在隔离 worker 运行 |
| model discovery | --help 的 --model 段暴露当前账号/环境支持项 | 运行时探测，不维护静态清单 |

官方参考：

- https://www.codebuddy.cn/docs/cli/sdk-python
- https://www.codebuddy.cn/docs/cli/cli-reference

### 1.2 支持基线

| 组件 | 首版基线 | 运行时策略 |
|---|---|---|
| Python SDK | codebuddy-agent-sdk 0.3.205 | 项目依赖固定版本 |
| CLI | 2.118.2 | parser/golden 调研基线；实际版本动态记录 |
| Python | 项目现有支持范围 | worker 使用项目运行环境 |
| 事件协议 | 调研样本对应的 stream-json | 未知事件保留 raw/audit，不扩展 FCMP 名称 |

调研文档和现有 stdout 样本仅用于证据定位。不得把历史 token、宿主配置、完整 trace、plugin marketplace 或 session state复制进本工件或 fixtures。

## 2. 已锁定决策与延期范围

### 2.1 已锁定

- 对外引擎名为 codebuddy。
- 国内版与国际版是两个虚拟 provider，而非两个 engine。
- provider_id 是网络环境、credential、配置目录、session resume 和模型目录的统一路由键。
- 国内版映射 internal，国际版映射 public；服务端不接受任意 environment。
- 官方 SDK 只能在白名单环境的隔离 helper 子进程运行。
- token 存储到服务级 Secret Vault，普通数据库和公共接口只保存/返回状态投影。
- 模型通过带 credential 的 provider 分区 probe 获取。
- MCP 始终使用 run-local generated config 和 strict 模式。
- CodeBuddy 首版不提供 inline TUI。
- 缓存继续由调用方控制，不自动 no_cache，不把账号或 credential generation 加入 key。
- 不新增 Runtime/FCMP/RASP event type。

### 2.2 延期

- iOA、企业域、自定义 endpoint/base URL。
- API key、apiKeyHelper、Client Credentials。
- 宿主登录、宿主 keyring、宿主 CodeBuddy 配置复用。
- worktree、tmux、sandbox、serve、ACP。
- 多租户 credential ownership 和外部 KMS。
- 静态模型清单。

## 3. Provider 路由矩阵

| provider_id | UI 名称 | SDK environment | Runtime environment | credential key | stable config dir |
|---|---|---|---|---|---|
| codebuddy-cn | CodeBuddy 国内版 | internal | internal | providers.codebuddy-cn | <agent_home>/.codebuddy-runtime/codebuddy-cn |
| codebuddy-global | CodeBuddy 国际版 | public | public | providers.codebuddy-global | <agent_home>/.codebuddy-runtime/codebuddy-global |

路由不变量：

1. job/auth/model 均只接受表内 canonical ID。
2. 缺失或无效 provider 在 cache lookup 和 subprocess spawn 之前失败。
3. 显式 engine_options.provider_id 优先于 model selector 和 parser fallback。
4. start、resume、probe 使用相同 provider config directory。
5. 替换账号或删除 credential 只轮换对应 provider 的 config/session state。

## 4. 进程与数据流

### 4.1 登录、credential 与模型刷新

    UI/API auth start
      -> provider registry 校验 provider_id
      -> sdk_auth_flow 创建隔离 worker
      -> worker temporary HOME/XDG/CODEBUDDY_CONFIG_DIR
      -> SDK authenticate(internal|public)
      -> 父进程接收 auth URL
      -> auth session = waiting_user
      -> worker wait 得到 token/user_id
      -> private pipe 交付父进程
      -> credential_store 原子写入 provider entry
      -> 若账号变化，轮换对应 stable config dir
      -> catalog_service 只刷新该 provider
      -> auth session = succeeded

失败、取消或超时路径必须在写 vault 之前终止 worker/CLI descendants 并清除 temporary directory。

### 4.2 Run start/resume

    job request
      -> engine-local request policy
          -> provider required and canonical
          -> vault state present/not advisory-expired
          -> reserved runtime env keys absent
      -> existing cache policy
      -> workspace materialization
          -> CODEBUDDY.md
          -> .codebuddy/settings.json
          -> .codebuddy/mcp.json
          -> .codebuddy/skills/<skill-id>
      -> command builder
      -> execution env builder
          -> remove inherited CodeBuddy routing/credential keys
          -> inject token/environment/stable config dir
      -> fresh CodeBuddy subprocess
      -> shared stream framer
      -> CodeBuddy parser
      -> Runtime events
      -> FCMP public flow + RASP audit

Resume 只在 command builder 增加 -r <session-id>，其余受管参数、provider 和 cwd 不变。

### 4.3 Secret 允许流向

| 读取者 | 允许读取 raw token | 允许输出 raw token |
|---|---:|---:|
| sdk auth parent flow | 是，仅接收新 token | 否 |
| credential_store | 是 | 否 |
| adapter env builder | 是 | 仅 subprocess environment |
| model probe env builder | 是 | 仅 subprocess environment |
| API/UI/status | 否 | 否 |
| logs/audit/bundle/golden/raw probe | 否 | 否 |

## 5. 目录与持久化路径

| 作用 | 路径 | 生命周期 | 权限/内容约束 |
|---|---|---|---|
| Vault root | <data_dir>/engine_credentials | 服务级 | 0700 |
| Vault file | <data_dir>/engine_credentials/codebuddy.json | 服务级 | 0600、atomic replace |
| 国内 stable config | <agent_home>/.codebuddy-runtime/codebuddy-cn | credential/account 生命周期 | provider 独占 |
| 国际 stable config | <agent_home>/.codebuddy-runtime/codebuddy-global | credential/account 生命周期 | provider 独占 |
| Catalog aggregate | <model-cache>/codebuddy/catalog.json | LKG | 不含 token |
| 国内 raw help | <model-cache>/codebuddy/codebuddy-cn/help.raw | probe evidence | 先做 token 全文扫描 |
| 国际 raw help | <model-cache>/codebuddy/codebuddy-global/help.raw | probe evidence | 先做 token 全文扫描 |
| Run instruction | <run_dir>/CODEBUDDY.md | run | shared prompt builder 输出 |
| Run settings | <run_dir>/.codebuddy/settings.json | run | system-owned |
| Run MCP | <run_dir>/.codebuddy/mcp.json | run | system-generated |
| Run skills | <run_dir>/.codebuddy/skills/<skill-id> | run | profile-driven materialization |
| Worker temp | OS temp/codebuddy-auth-* | 单 auth session | 无论终态均删除 |

Vault version 1 逻辑结构：

    version: 1
    providers:
      <provider_id>:
        token: secret
        user_id: SDK user id
        updated_at: UTC timestamp
        expires_at_advisory: UTC timestamp or null
        sdk_version: 0.3.205
        cli_version: observed value or null

## 6. API、内部接口与 Schema 变更

### 6.1 公共 API

| 接口 | 变更 | 合同 |
|---|---|---|
| POST jobs | 复用 engine_options.provider_id | CodeBuddy 必须是两个 canonical provider 之一 |
| auth session start/read/cancel | 复用现有 oauth_proxy/auth_code_or_url | provider-specific，no manual input |
| GET /v1/engines/codebuddy/models | 新 engine 路由结果 | provider-qualified records |
| management engine summary/detail | 扩展 CodeBuddy 与 credential projection | 永不返回 token |
| DELETE /v1/management/engines/{engine}/auth/credentials/{provider_id} | 新增 | 仅 codebuddy canonical provider 可删除 |

Credential delete response：

    {
      "engine": "codebuddy",
      "provider_id": "codebuddy-cn",
      "deleted": true,
      "credential_state": "missing"
    }

### 6.2 内部接口

| 模块 | 主要接口 | 责任 |
|---|---|---|
| auth/provider_registry.py | require_provider, get_provider | canonical ID 与 environment SSOT |
| auth/credential_store.py | get, put, delete, project_status | 原子 secret persistence 与脱敏 |
| auth/sdk_worker.py | worker protocol main | 隔离 SDK 和 CLI transport |
| auth/sdk_auth_flow.py | start, wait, cancel | worker 生命周期和 vault commit |
| auth/runtime_handler.py | attach/start hooks | generic auth runtime 对接 |
| models/catalog_service.py | refresh_provider, refresh_logged_in, list_models | provider probe 与 LKG |
| adapter/command_builder.py | build_start, build_resume | 受管 argv 合同 |
| adapter/config_composer.py | materialize_settings_and_mcp | run-local system config |
| adapter/stream_framer.py | feed, finish | stateful JSONL framing |
| adapter/stream_parser.py | parse_frame, finalize | Runtime/terminal/auth mapping |
| adapter/execution_adapter.py | request policy/env/command/parser | adapter orchestration |

### 6.3 机器合同

| 文件 | 变更 |
|---|---|
| server/contracts/schemas/adapter_profile_schema.json | engine 增 codebuddy；provider_contract.selection_required；ui_shell.enabled |
| server/contracts/schemas/skill/skill_runner_manifest.schema.json | engine enum 增 codebuddy |
| server/contracts/schemas/mcp_registry.schema.json | engine enum 增 codebuddy |
| server/contracts/invariants/runtime_parser_capabilities.yaml | CodeBuddy parser capability row |
| server/contracts/schemas/runtime_contract.schema.json | 当前不改；只有新增协议字段/event 时先改 |
| server/contracts/invariants/session_fcmp_invariants.yaml | 当前不改；只有状态/event 语义变化时先改 |

## 7. CLI 命令合同

### 7.1 Start

    codebuddy -p
      --output-format stream-json
      --permission-mode bypassPermissions
      --settings <run_dir>/.codebuddy/settings.json
      --setting-sources project
      --mcp-config <run_dir>/.codebuddy/mcp.json
      --strict-mcp-config
      [--json-schema <inline-json>]
      [--model <runtime-model>]
      <prompt>

### 7.2 Resume

    codebuddy -p
      --output-format stream-json
      --permission-mode bypassPermissions
      -r <session-id>
      --settings <run_dir>/.codebuddy/settings.json
      --setting-sources project
      --mcp-config <run_dir>/.codebuddy/mcp.json
      --strict-mcp-config
      [--json-schema <inline-json>]
      [--model <runtime-model>]
      <reply>

### 7.3 命令不变量

- prompt/reply 是最终 argv 元素，禁止 shell 拼接。
- start 与 resume 使用同一 provider stable config dir。
- cwd 固定为 run_dir。
- 每次 attempt 是 fresh subprocess。
- 不生成 --continue、--worktree、--worktree-branch、--tmux、--sandbox、--serve、--acp。
- 即使没有 MCP server，也生成空 mcpServers 并传 strict config。

settings.json 固定值：

    {
      "autoUpdates": false,
      "disableAllHooks": true,
      "allowUntrustedFrontmatterHooks": false,
      "enableAllProjectMcpServers": false
    }

## 8. JSONL 到 Runtime/FCMP/RASP 映射

| CodeBuddy 输入 | Parser 产物 | Runtime/FCMP/RASP 语义 | 关键约束 |
|---|---|---|---|
| system.init | run handle + turn start | session/run handle；conversation turn 开始 | 首个有效 session_id 为 canonical；重复 init 合法 |
| assistant.thinking | reasoning candidate | assistant process/reasoning | 不提升为最终文本 |
| assistant.text | message candidate | assistant message/final candidate | 仅真实 text 可被 promotion |
| assistant.tool_use | process event | tool/command process | 保留 tool id/name/input 的结构化摘要 |
| user.tool_result | process result | tool result process | 与 tool_use 关联但不锁内部顺序 |
| result.success 且 is_error=false | terminal complete | turn complete | process exit 0 不足以替代此事件 |
| result error subtype | terminal failed | turn failed | exit 0 仍失败 |
| 任意 result 且 is_error=true | terminal failed | turn failed | 解析 auth/terminal error |
| result.structured_output | structured result | shared structured-output pipeline | 不从文本重建 |
| file-history-snapshot | raw event | RASP/raw audit only | 不生成用户可见 FCMP |
| ai-title | raw event | RASP/raw audit only | 不生成用户可见 FCMP |
| unknown valid event | raw event + diagnostic metadata | audit-preserving | 不发明 FCMP event type |
| malformed frame | diagnostic | parser/raw audit | 允许后续独立合法 event resync |

共享 mapper 只处理无 engine 身份的 content block：thinking/reasoning、text、tool_use、tool_result。Claude 和 CodeBuddy 分别保留 framing、session、auth 与 terminal 状态机。

## 9. 失败矩阵

### 9.1 Auth

| 条件 | 检测位置 | 对外结果 | 清理/副作用 |
|---|---|---|---|
| provider 缺失/无效 | request policy | 结构化 validation error | 不查 cache、不 spawn |
| credential missing | request policy | auth required，指向对应 provider | 不查 cache、不 spawn |
| advisory expired | request policy/status | auth required 或 expired | 不删除 token；等待 reauth |
| SDK 无 URL | sdk worker/flow | auth failed | 杀 descendants，删 temp |
| 用户未在期限内完成 | auth flow | expired | 杀 descendants，删 temp |
| 用户取消 | auth flow | canceled | 杀 descendants，删 temp |
| SDK stderr 含 token | redactor | sanitized failure | 原文不得写日志 |
| 新账号替换旧账号 | vault commit | succeeded | 原子写 vault，轮换该 provider config |
| runtime 401/login prompt | parser auth detector | waiting_auth，高置信 provider signal | 保留 session handle，等待对应 provider reauth |

### 9.2 Terminal/process

| terminal event | exit code | 结果 |
|---|---:|---|
| success + is_error=false | 0 | complete |
| success + is_error=false | 非 0 | failed，process failure 优先 |
| error subtype | 0/非 0 | failed |
| is_error=true | 0/非 0 | failed |
| 无 result | 0 | failed：missing terminal result |
| 无 result | 非 0 | failed：process + missing terminal diagnostic |

### 9.3 Timeout/cancel

| 场景 | 行为 |
|---|---|
| runtime timeout | 终止 fresh subprocess；产生 timeout terminal；不得伪造 result success |
| runtime cancel | 终止 subprocess；产生 canceled；不得 fallback promotion |
| auth timeout/cancel | 终止 worker 与 CLI descendants，清除 temp，不写 vault |
| model probe timeout | 终止 probe；记录 error；保留 provider LKG |

### 9.4 Malformed stream

| 输入 | Framer 行为 | Parser 行为 |
|---|---|---|
| 正常 JSONL | 每行一 frame | 正常映射 |
| JSON string 内物理换行 | 转义为逻辑换行并保留 raw byte range | 映射 repaired event，记录诊断/provenance |
| 独立坏行 | 生成 malformed diagnostic | 不吞后续 event |
| 超限行 | 生成 over-limit diagnostic 并进入 resync | 不无限缓存 |
| EOF 未闭合 | finish 生成 unterminated diagnostic | 无 terminal 时失败 |
| 坏行后 system.init/result | 从后续独立合法 JSON resync | handle/terminal 仍可生效 |

## 10. 代码级文件清单

### 10.1 新增

| 路径 | 内容 |
|---|---|
| openspec/changes/add-codebuddy-code-engine/** | proposal、design、tasks、16 个 delta specs |
| artifacts/codebuddy_engine_integration_plan_2026-07-10.md | 本代码级计划 |
| server/engines/codebuddy/__init__.py | engine package |
| server/engines/codebuddy/auth/provider_registry.py | provider SSOT |
| server/engines/codebuddy/auth/credential_store.py | vault |
| server/engines/codebuddy/auth/sdk_worker.py | 隔离 SDK worker 协议 |
| server/engines/codebuddy/auth/sdk_auth_flow.py | worker 管理与 vault commit |
| server/engines/codebuddy/auth/runtime_handler.py | auth runtime hook |
| server/engines/codebuddy/models/catalog_service.py | provider 模型探测/LKG |
| server/engines/codebuddy/adapter/adapter_profile.json | profile |
| server/engines/codebuddy/adapter/execution_adapter.py | runtime adapter |
| server/engines/codebuddy/adapter/command_builder.py | start/resume argv |
| server/engines/codebuddy/adapter/config_composer.py | settings/MCP materialization |
| server/engines/codebuddy/adapter/stream_framer.py | stateful framing |
| server/engines/codebuddy/adapter/stream_parser.py | event/terminal/auth mapping |
| server/engines/codebuddy/config/*.json/yaml | auth/default/bootstrap/enforced |
| server/engines/common/content_block_mapper.py | Claude/CodeBuddy shared block mapper |
| tests/unit/test_codebuddy_*.py | provider/vault/auth/catalog/adapter/parser tests |
| tests/engine_integration/golden/codebuddy/** | 脱敏 fixtures 与 expectations |
| 必要的 API response model | credential delete redacted response |

### 10.2 修改

| 路径/区域 | 变更 |
|---|---|
| pyproject.toml 与现有 lock | 固定 SDK 0.3.205 |
| server/contracts/schemas/** | engine/profile/manifest/MCP vocabulary |
| server/contracts/invariants/runtime_parser_capabilities.yaml | parser row |
| server/runtime/adapter/common/profile_loader.py | selection_required、ui_shell.enabled |
| server/runtime/adapter/common/prompt_builder_common.py | CODEBUDDY.md |
| server/runtime/adapter/base_execution_adapter.py 或 request-policy 扩展点 | cache 前 policy、managed env 约束 |
| server/config_registry/keys.py | 最终 active key |
| server/services/engine_management/** | adapter/auth/model/install/status/upgrade registration |
| server/services/orchestration/run_auth_orchestration_service.py | explicit provider 优先 |
| server/services/mcp/registry.py | CodeBuddy root/type/empty config |
| server/services/ui/engine_shell_capability_provider.py | enabled=false |
| management/engines/UI routers、models、templates、locales | credential 与 provider UX |
| agent_harness/skill_injection.py 与 integration harness | CodeBuddy profile/golden |
| README、adapter/auth/API/runtime/MCP/test docs | 用户与开发者合同 |
| 根 AGENTS.md | 修正 runtime SSOT 路径漂移 |

### 10.3 删除

不计划删除现有文件。不得回滚或覆盖 artifacts 目录中已有的调查/probe/stdout 未提交改动。

## 11. 四阶段任务与依赖

本节中的任务 ID 必须与 tasks.md 一致；这里只描述实施细节，不记录完成状态。

### 阶段一：规格、合同与计划

#### CB-1.1 Umbrella change 与详细计划

依赖：无。

实施：

- 创建 proposal、design、16 个 delta specs 和 tasks。
- 创建本文并引用调查工件，不复制敏感 evidence。
- 固化 precedence、provider matrix、command/event/failure/test contract。

验收：OpenSpec 能识别全部 artifacts；tasks 仅保留 ID、摘要、链接和状态。

#### CB-1.2 机器合同与导航

依赖：CB-1.1。

实施：

- profile schema 增 codebuddy、selection_required、ui_shell.enabled。
- skill/MCP schema 墳 codebuddy。
- parser capability invariants 增 CodeBuddy 预声明 row；parser/profile 落地并激活后再转入活动 engine row。
- profile loader 对旧 profile 提供 selection_required=false、ui_shell.enabled=true 默认。
- 根 AGENTS.md 的 schema/invariants 导航指向 server/contracts 当前路径。

验收：严格 OpenSpec 验证、schema/profile/parser capability 合同测试通过；不新增 runtime event。

### 阶段二：Provider、Vault、Auth 与模型

#### CB-2.1 Provider 与 Secret Vault

依赖：CB-1.2。

实施：

- provider_registry 是 canonical provider/environment 唯一事实源。
- credential_store 提供原子 CRUD、advisory expiry、status projection。
- 目录/文件权限和 symlink/path safety 纳入实现。
- 账号替换与 credential delete 轮换 provider config state。

验收：双 provider 不串用；权限、原子写、删除、状态和 token redaction 测试通过。

#### CB-2.2 隔离 SDK auth worker

依赖：CB-2.1。

实施：

- 增加固定项目依赖并同步项目现有 lock（若仓库存在 lock）。
- worker 清理环境，只保留执行所需系统变量，创建 temporary HOME/XDG/config。
- 父子协议只发送 URL、终态和最终 credential payload；token payload 不进入持久 stdout。
- runtime handler 接入 oauth_proxy/auth_code_or_url；成功后写 vault 并刷新单 provider catalog。
- 处理 one-active-session-per-provider、cancel、timeout、descendant cleanup 和 stderr redaction。

验收：URL/success/failure/timeout/cancel、temp cleanup、日志脱敏和 provider routing 测试通过。

#### CB-2.3 Provider 分区模型目录

依赖：CB-2.1；auth success hook 依赖 CB-2.2。

实施：

- 使用 selected provider credential/environment/config dir 运行 --version 和 --help。
- 解析 --model Currently supported 段，生成 provider-qualified record。
- provider snapshot 独立保存，失败保留 LKG，从未成功返回空列表。
- 登录成功只刷新当前 provider；手工/定时刷新所有已登录 provider。

验收：同名模型不冲突、单 provider failure 不影响另一 provider、raw probe 无 token。

### 阶段三：Adapter、Workspace、MCP 与 Parser

#### CB-3.1 Request policy、workspace 与 command adapter

依赖：CB-2.1、CB-2.3。

实施：

- 创建 profile、bootstrap/default/enforced config 和 execution adapter。
- cache 前强制 provider/credential/reserved env policy。
- build env 时清除 inherited CodeBuddy keys，再注入受管值。
- materialize CODEBUDDY.md、settings、MCP 与 skills。
- 实现 start/resume 对称命令，fresh subprocess、cwd=run_dir。

验收：argv、cwd、provider env/config、workspace、no model fallback 和 reserved env tests 通过。

#### CB-3.2 受管 MCP 与 structured output

依赖：CB-3.1。

实施：

- registry 增 CodeBuddy mcpServers root 和 transport type。
- 无 server 仍生成空 config；start/resume 永远 strict。
- 复用 MCP secret resolver，禁止 secret 回显。
- --json-schema inline 编码和 result.structured_output 接入 shared pipeline。

验收：STDIO/HTTP/SSE、empty strict config、secret redaction 和 structured-output tests 通过。

#### CB-3.3 Stateful framer、parser 与协议映射

依赖：CB-3.1；structured terminal 依赖 CB-3.2。

实施：

- framer 支持 byte ranges、physical-newline repair、line limit、EOF diagnostic、independent event resync。
- parser 映射 init/thinking/text/tool/result/raw-only 事件。
- 终态要求 terminal result；exit-zero error 和 missing result 失败。
- auth detector 发高置信 signal；auth orchestration 显式 provider 优先。
- 抽取 engine-neutral content-block mapper，Claude 与 CodeBuddy 共享；保留各自 framing/terminal/auth。

验收：live/batch 共用 framer，坏行不吞 init/result，resume repeated init，Claude 无行为回归。

### 阶段四：Activation、API/UI、Golden 与发布

#### CB-4.1 中央登记、管理面与 Harness

依赖：全部阶段二、三任务。

实施：

- 一次性加入 active engine key、adapter registry、install/upgrade/status、auth bootstrap、provider registry、model lifecycle 和 config bootstrap。
- 管理 detail 暴露 provider credential projection；增加 provider credential delete endpoint。
- UI 增安装/版本与双入口 login/relogin/clear；job provider-first/model-filter；禁用 inline TUI。
- locales 增中英法日标签与结构化错误语义。
- harness/manifest/MCP UI 增 CodeBuddy。

验收：engine 在全部登记点一致可见；不存在“可选但不可执行”状态；credential 不回显。

#### CB-4.2 Golden、测试、文档与发布 gate

依赖：CB-4.1。

实施：

- 从 ignored native-pipe evidence 生成脱敏 golden：success、resume/repeated init、thinking/text/tools、structured、exit-zero auth error、cancel、runtime error、malformed/resync。
- 两个历史 malformed fixture 标记 provenance-unverified。
- 更新 README、adapter reference、onboarding、auth driver、API、runtime env、MCP 和 test specification。
- 运行 strict OpenSpec、focused、runtime SSOT、golden 和 token scan。
- 用专用账号执行国内/国际 manual gate。

验收：自动 gate 全绿；人工 gate 逐项留证。缺少国际账号时不得标记国际人工验证完成。

### 11.1 依赖图

    CB-1.1
      -> CB-1.2
          -> CB-2.1
              -> CB-2.2
              -> CB-2.3
              -> CB-3.1
                  -> CB-3.2
                  -> CB-3.3
                      -> CB-4.1
                          -> CB-4.2

CB-2.2 与 CB-2.3 可在 provider/vault 稳定后并行；CB-3.2 与 framer 的非 structured 部分也可并行，但中央登记必须等待完整阶段三。

## 12. 验证矩阵

### 12.1 自动测试

| 行为 | Unit | API/contract | Golden |
|---|---:|---:|---:|
| provider 必选/canonical routing | 是 | 是 | 否 |
| vault permission/atomic/delete | 是 | 否 | 否 |
| SDK URL/success/failure/cancel | 是 | auth contract | 否 |
| token 不泄漏 | 是 | API redaction | evidence scan |
| provider config/session isolation | 是 | 否 | resume |
| catalog partition/LKG | 是 | models API | 否 |
| workspace/argv | 是 | profile contract | start/resume |
| strict MCP | 是 | MCP schema | start |
| structured output | 是 | runtime protocol | structured |
| thinking/text/tool mapping | 是 | FCMP/RASP | 是 |
| exit-zero error | 是 | runtime protocol | 是 |
| missing terminal/cancel/timeout | 是 | state invariants | 是 |
| malformed/resync | 是 | parser capabilities | 是 |
| install/status/upgrade | 是 | management API | 否 |
| provider UI/model filter/no TUI | UI route/js | management API | 否 |

### 12.2 核心命令

    openspec validate add-codebuddy-code-engine --strict

    conda run --no-capture-output -n DataProcessing python -u -m pytest +      tests/unit/test_codebuddy_adapter.py +      tests/unit/test_codebuddy_auth_flow.py +      tests/unit/test_codebuddy_credential_store.py +      tests/unit/test_codebuddy_model_catalog_service.py +      tests/unit/test_engine_adapter_registry.py +      tests/unit/test_engine_auth_flow_manager.py +      tests/unit/test_engine_auth_strategy_service.py +      tests/unit/test_model_registry.py +      tests/unit/test_mcp_config_governance.py +      tests/unit/test_runtime_parser_capability_contract.py +      tests/unit/test_runtime_event_protocol.py +      tests/unit/test_agent_cli_manager.py +      tests/unit/test_ui_routes.py

    conda run --no-capture-output -n DataProcessing python -u -m pytest +      tests/unit/test_session_invariant_contract.py +      tests/unit/test_session_state_model_properties.py +      tests/unit/test_fcmp_mapping_properties.py +      tests/unit/test_protocol_state_alignment.py +      tests/unit/test_protocol_schema_registry.py +      tests/unit/test_runtime_event_protocol.py +      tests/unit/test_run_observability.py

    ./tests/engine_integration/run_engine_integration_tests.sh -e codebuddy

测试文件名应以实际仓库落地为准；不存在的计划目标测试需在任务实施时创建或将验证合并到稳定的现有测试，避免重复和实现细节测试。

### 12.3 人工发布验证

1. 国内版登录成功。
2. 国际版登录成功。
3. 两个 provider 模型目录独立刷新。
4. 两个 provider 分别完成首轮执行。
5. fresh subprocess 使用精确 session resume。
6. 401 路由到对应 provider reauth。
7. 清除 credential 后旧 session 不再恢复。
8. auth/probe/run evidence 完成 raw token 全文扫描且无泄漏。

## 13. 阶段门禁与回滚边界

| 阶段 | 进入条件 | 完成条件 | 回滚边界 |
|---|---|---|---|
| 一 | 调研文档可读、决策锁定 | OpenSpec strict；合同测试通过；详细计划完整 | 删除未激活的 change/contract 增量；不碰调查文件 |
| 二 | profile/schema 能描述 CodeBuddy | provider/vault/auth/catalog focused tests 通过 | 不注册 active engine；保留或显式删除 vault，绝不静默清理 |
| 三 | provider/vault 接口稳定 | adapter/MCP/parser/Claude regression 通过 | adapter 保持未登记；provider secrets 不受影响 |
| 四 | 所有执行链自动测试通过 | 全局登记一致、golden/docs、自动和可用人工 gate 完成 | 先撤 active registry/UI；再按需撤 adapter；不自动删除 credential |

任何阶段若发现必须新增 Runtime event/field，应停止实现，先修改 runtime_contract schema、session invariants、sequence/spec 和合同测试。

## 14. 后续 Agent Handoff 规则

每次 agent 接手必须：

1. 先读 change 的 proposal、design、全部相关 delta specs、tasks.md 和本文对应任务。
2. 检查 git status，保护既有未提交调查/probe/stdout 改动。
3. 只执行 tasks.md 中一个或一组依赖已满足的稳定任务 ID。
4. 先检查更高优先级合同；发现冲突时不得以本文覆盖 specs。
5. 使用 provider_registry 作为 ID/environment SSOT，禁止复制映射。
6. 使用 credential_store 和 MCP secret resolver，禁止新增旁路 secret persistence。
7. 不在业务层手拼 FCMP/RASP payload；复用 protocol factories。
8. 不把 token、完整 trace、宿主 config 或 session state加入测试 fixture。
9. 运行任务对应的最小测试；失败时记录命令、根因和未解决项。
10. 只有在代码和验收均完成后勾选 tasks.md；本文不添加完成标记。

Handoff 摘要必须包含：任务 ID、修改文件、接口变化、验证命令/结果、未完成外部 gate、是否触及 machine contract、是否做过 token scan。

## 15. 未解决外部条件

- 国际版专用测试账号尚需提供；没有账号只能完成代码与自动测试，不能完成国际 manual release gate。
- 国内版与国际版账号应是专用测试身份，禁止使用开发者个人宿主登录作为 evidence。
- 测试环境需要能安装/发现 CodeBuddy CLI；离线 CI 只运行 mocked/golden 层。
- CLI 服务端模型列表可能随账号和时间变化；发布验收记录实际 CLI 版本与采集时间，不锁模型全集。
- SDK/CLI 上游协议变化若超出 0.3.205/2.118.2 证据范围，应先更新调查与 golden，再放宽 parser。

## 16. 发布前最终检查

- machine contract、spec、design、本文和代码无 provider 命名漂移。
- active engine registry 与 adapter/auth/model/install/UI 集合一致。
- CodeBuddy UI shell capability 为 disabled。
- runtime_options.env 保留项在 cache 前拒绝。
- start/resume/probe 全部使用 selected provider stable config。
- 任何 exit 0 error 和 missing result 都不会成功。
- malformed row 后合法 terminal 能 resync。
- vault/probe/golden/bundle/log 完成 token scan。
- 缓存跨账号风险已进入用户/开发者文档。
- 国际 manual gate 状态如实记录。
