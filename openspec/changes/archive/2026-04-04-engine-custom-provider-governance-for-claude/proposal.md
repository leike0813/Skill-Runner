## Why

Claude Code 的官方订阅成本很高，用户经常会把 Claude Code 搭配第三方 provider 使用。当前 Skill Runner 的 Claude 接入只覆盖官方 OAuth / CLI 登录路径，缺少以下关键治理能力：

- 无法在 managed agent home 中维护第三方 provider 配置
- Claude bootstrap 仍把 bootstrap 文件语义绑定到 `.claude/settings.json`，无法初始化 `.claude.json.hasCompletedOnboarding`
- Claude model catalog 只能返回官方快照模型，无法暴露第三方 provider 模型
- 当 job 请求 `provider/model` 时，系统无法进入专门的第三方 provider 配置会话，只能走官方 auth 或直接失败
- harness / E2E 也缺少 `provider/model` 的一等公民支持

这些缺口会让“官方模型鉴权”和“第三方 provider 配置”混在一起，既不清晰，也不利于未来把同样的治理模型拓展到 `codex` 等其他 engine。

## What Changes

- 新增通用语义的 engine custom-provider 服务层与 management API，当前只注册 Claude 实现
- Claude bootstrap 改为初始化 `agent_home/.claude.json`，写入 `hasCompletedOnboarding=true`
- Claude runtime model 注入统一改为 `run-local .claude/settings.json.env`
- Claude model catalog 改为“官方快照 + custom provider”合并视图，并新增 `source`
- 管理 UI 引擎页新增 Claude custom provider CRUD 区域
- 第三方 Claude 模型进入独立的 provider-config auth session，而不是复用官方 OAuth / CLI 登录
- `agent_harness` 新增 `--custom-model`，当前仅对 Claude 有效
- E2E run form 改为消费 Claude merged catalog，并支持提交 `provider/model`

## Capabilities

### New Capabilities

- None

### Modified Capabilities

- `engine-auth-observability`: Claude 新增 `provider_config/custom_provider` 会话路径，与官方 auth 分离
- `engine-status-cache-management`: Claude model catalog 改为官方模型与 custom provider 模型合并视图
- `ui-engine-management`: 管理 UI 引擎页支持 Claude custom provider CRUD
- `builtin-e2e-example-client`: E2E run form 支持 Claude `provider/model`
- `external-runtime-harness-cli`: harness 支持 `--custom-model`（当前仅 Claude）
- `local-deploy-bootstrap`: Claude bootstrap 初始化 `.claude.json.hasCompletedOnboarding=true`

## Impact

- Affected code:
  - `server/services/engine_management/*`
  - `server/engines/claude/**`
  - `server/routers/management.py`
  - `server/routers/ui.py`
  - `e2e_client/*`
  - `agent_harness/*`
- Public observable changes:
  - 新增 `/v1/management/engines/{engine}/custom-providers` CRUD
  - Claude engine detail / model list 会暴露 merged catalog 与 `source`
  - 第三方 Claude 模型问题会进入独立 `provider_config/custom_provider` waiting_auth 路径
