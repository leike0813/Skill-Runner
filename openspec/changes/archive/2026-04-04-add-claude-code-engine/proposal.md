# add-claude-code-engine Proposal

## Summary

新增 `claude` 作为新的完整一等公民 engine，接入执行、鉴权、engine 管理、模型目录、管理 UI 与 E2E 示例客户端。

本次实现遵守现有解耦红线：

- engine-specific 代码收敛在 `server/engines/claude/**`
- 只允许在集中注册点扩展 `claude`
- 不把新的 `if engine == "claude"` 分支扩散到 runtime / orchestration 主干

## Motivation

当前系统仅支持 `codex`、`gemini`、`iflow`、`opencode`。为了让 Skill Runner 能稳定托管 Claude Code，会话执行、鉴权与管理链路都需要把 `claude` 作为一等公民接入，而不是以临时兼容逻辑旁路实现。

同时，管理 UI 当前仍有多处 engine 条件分支。如果直接为 Claude 继续堆模板分支，会进一步恶化耦合边界。本次 change 需要顺手把这些热点收敛到 metadata-driven 方式。

## Scope

- 新增 `server/engines/claude/**` 完整引擎包
- managed npm 安装 `@anthropic-ai/claude-code`
- 非交互执行走 `claude -p --output-format stream-json --verbose`
- 静态模型 manifest / snapshot
- 完整 auth 接入：
  - `oauth_proxy`
  - `cli_delegate`
- 管理域与 UI / E2E 暴露 `claude`
- 收敛 UI engine auth 热点为 metadata-driven

## Non-Goals

- 不修改 runtime / orchestration 主流程以适配 Claude 专有分支
- 不做 Claude 模型 runtime probe
- 不引入新的 auth transport 类型
- 不实现运行中的自动安装 / 自动补装

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `engine-adapter-runtime-contract`: 新增 `claude` adapter contract
- `engine-auth-observability`: 新增 `claude` auth transport / observability
- `engine-upgrade-management`: 新增 `claude` managed install/upgrade
- `engine-status-cache-management`: 状态缓存与 auth/status 观测纳入 `claude`
- `ui-engine-management`: UI engine 管理页支持 `claude`
- `builtin-e2e-example-client`: E2E client 可选择 `claude`
- `local-deploy-bootstrap`: bootstrap/install/preflight/doctor/status 纳入 `claude`

## Impact

- Affected code:
  - `server/engines/claude/**`
  - `server/services/engine_management/*`
  - `server/routers/ui.py`
  - `server/assets/templates/ui/*`
  - `e2e_client/*`
- Public observable changes:
  - engine 枚举新增 `claude`
  - 管理 UI 可安装/升级/鉴权 Claude
  - E2E run form 可选择 Claude
