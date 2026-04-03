# claude-engine-runtime-governance-refinement Proposal

## Summary

对 `claude` engine 做一轮完整的运行治理收口，覆盖命令默认参数、bootstrap/default/enforced 配置分层、headless 与 `ui_shell` 的差异化权限/沙箱策略，以及 Claude settings 的真实 schema 校验接入。

## Motivation

Claude 当前虽然已经接入执行、trust、custom provider 与 harness，但运行治理还没有完全收口：

- `ui_shell` 仍走 fallback/noop 能力
- headless 与 `ui_shell` 的权限姿态尚未分治
- Claude settings 仍在使用旧的简化配置校验链，无法正确理解官方 schema
- bootstrap 的全局状态文件与 runtime settings 文件的职责边界还不够清晰

这些问题会让 Claude 的行为与现有其他 engine 的治理水平不一致，也会继续产生误导性 schema warning。

## Scope

- 收紧 Claude `command_defaults`
- 明确 `.claude.json` 与 `run_dir/.claude/settings.json` 的配置分层
- 为 headless/harness 写入宽权限但 run-local 限写的 sandbox 规则
- 为 `ui_shell` 新增专用 capability 与严格权限策略
- 将 Claude config 校验切到真实 JSON Schema

## Non-Goals

- 不改变 Claude `stream-json` 作为 headless 主输出协议
- 不新增网络域 allowlist 精细治理
- 不改变官方/第三方 provider 的模型注入路线
- 不把非容器部署宣传为强隔离方案

## Capabilities

### Modified Capabilities

- `engine-adapter-runtime-contract`
- `ui-engine-management`

## Impact

- Affected code:
  - `server/engines/claude/**`
  - `server/engines/common/config/json_layer_config_generator.py`
  - `server/services/ui/engine_shell_capability_provider.py`
  - `tests/unit/*claude*`
- Public observable changes:
  - Claude `ui_shell` 不再走 fallback/noop 安全策略
  - Claude headless run/harness 会生成更明确的 sandbox filesystem 限写配置
  - Claude config 不再出现 `Key 'env' not found in schema` 这类伪警告
