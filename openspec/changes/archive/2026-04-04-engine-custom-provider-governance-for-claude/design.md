## Context

Claude 的官方鉴权与第三方 provider 配置是两套不同的治理面：

- 官方模型依赖 Claude 官方 OAuth / CLI 登录
- 第三方模型依赖向 Claude settings 注入：
  - `ANTHROPIC_AUTH_TOKEN`
  - `ANTHROPIC_BASE_URL`
  - `ANTHROPIC_MODEL`

同时，Claude 还要求在全局状态文件 `.claude.json` 中标记 `hasCompletedOnboarding=true` 才能跳过首次启动时的登录门禁。这意味着：

- bootstrap 需要能写 agent-home 级别的全局状态文件
- runtime config 仍应只写 run-local `.claude/settings.json`
- 官方 auth 和第三方 provider 配置必须分离

## Goals / Non-Goals

**Goals**

- 用通用语义建立 engine custom-provider 服务层，当前先落地 Claude
- 在 bootstrap 阶段初始化 `.claude.json.hasCompletedOnboarding=true`
- Claude runtime 对官方/第三方模型统一走 `settings.json.env` 注入
- 管理 UI 引擎页支持 Claude custom provider CRUD
- 第三方 Claude 模型在 waiting_auth 中进入独立 provider-config 会话
- harness / E2E 能消费 Claude merged catalog

**Non-Goals**

- 不把这套 custom-provider 抽成所有 engine 立即共用的完整实现
- 不在 provider-config 会话内做主动可用性验证
- 不把第三方 provider CRUD 暴露到 E2E run form
- 不改变其他 engine 现有 auth transport 语义

## Decisions

### 决策 1：custom-provider 接口按多引擎语义命名

- 方案：服务、路由、数据模型统一使用 `engine custom providers`
- 原因：后续至少 `codex` 也要接这套能力，先避免命名债

### 决策 2：Claude bootstrap 与 runtime config 分层

- 方案：
  - `server/engines/claude/config/bootstrap.json` 目标是 `agent_home/.claude.json`
  - `server/engines/claude/adapter/config_composer.py` 仍只写 `run_dir/.claude/settings.json`
- 原因：`.claude.json` 是全局状态文件，不应由每次 run 动态修补

### 决策 3：模型传递统一收口到 `settings.json.env`

- 方案：
  - 官方模型：只注入 `ANTHROPIC_MODEL`
  - 第三方模型：注入 `ANTHROPIC_AUTH_TOKEN`、`ANTHROPIC_BASE_URL`、`ANTHROPIC_MODEL`
  - Claude CLI 不再依赖 `--model`
- 原因：第三方 provider 的模型选择无法稳定通过 CLI flag 传入，统一 env 更清晰

### 决策 4：第三方 provider 会话独立于官方 auth

- 方案：新增 `transport=provider_config`、`auth_method=custom_provider`
- 原因：官方 OAuth / CLI 登录与第三方 provider 配置是不同问题，混在一个 transport 会污染语义

### 决策 5：waiting_auth 采用“四选一 + 场景裁剪”

- 方案：provider-config 会话提供四个动作：
  1. `replace_api_key`
  2. `switch_model`
  3. `switch_provider`
  4. `configure_provider`
- 当前上下文决定哪些动作可见/可用
- 原因：这样能同时覆盖 token 过期、模型缺失、provider 缺失三类真实场景

## Architecture

### 1. Generic custom-provider layer

- `server/services/engine_management/engine_custom_provider_service.py`
  - 通用 facade / registry
- `server/engines/claude/custom_providers.py`
  - Claude engine-local 存储与匹配实现

当前只有 `claude` 注册：
- 持久化文件：`agent_home/.claude/custom_providers.json`
- 数据结构：
  - `providers[{provider_id, api_key, base_url, models[]}]`

### 2. Claude bootstrap

- Adapter profile 的 `bootstrap_target_relpath` 改为 `.claude.json`
- `bootstrap.json` 写入：
  - `hasCompletedOnboarding: true`

### 3. Merged model catalog

`model_registry` 对 Claude 走双源合并：

- 官方快照模型：
  - 保留原官方 bare id
  - `source=official`
  - 元数据补齐 `provider=anthropic`、`model=<official_id>`
- custom provider 模型：
  - 对外 id 统一为 `provider/model`
  - `source=custom_provider`

### 4. Provider-config auth session

新增 transport / method：

- `transport=provider_config`
- `auth_method=custom_provider`

会话阶段仍复用现有 waiting_auth 基础设施，但 Claude runtime handler 改为：

- 官方模型：继续走官方 OAuth / CLI 组合
- 第三方模型：进入 provider-config session

provider-config session 不主动验证 provider 是否可用。提交配置后直接视为成功，并通过现有 resume ticket 重试 run。

## Risks / Trade-offs

- [Risk] provider-config 会话新增 transport，会触达 auth strategy schema、UI 路由和 waiting_auth 编排  
  Mitigation: 保持 transport 语义独立，不污染官方 OAuth/CLI 流

- [Risk] Claude merged catalog 需要在多个入口保持一致  
  Mitigation: 所有读取统一走 `model_registry.get_models("claude")`

- [Risk] bootstrap 目标从 `.claude/settings.json` 改到 `.claude.json` 后，文档和测试容易漂移  
  Mitigation: 同步更新 bootstrap 测试与 Claude 文档，显式说明 bootstrap vs runtime config 的分层
