# ui-shell-security-governance-unification Design

## Design Overview

本次 change 把 `ui_shell` 分成两层合同：

1. **Adapter profile**
   - 声明 capability 元数据
   - 声明 CLI 默认参数
   - 声明 probe / auth hint / runtime override / config asset 的策略名
2. **Engine config assets**
   - 承载无法仅靠 CLI 表达的 session-local 配置

## Profile Contract

adapter profile 新增顶层 `ui_shell` 块，包含：

- `command_id`
- `label`
- `trust_bootstrap_parent`
- `sandbox_arg`
- `retry_without_sandbox_on_early_exit`
- `sandbox_probe_strategy`
- `sandbox_probe_message`
- `auth_hint_strategy`
- `runtime_override_strategy`
- `config_assets`

`command_defaults.ui_shell` 继续只负责 CLI 参数。

## Session Config

- `codex`：profile-only，无额外 session config 文件
- `gemini` / `iflow` / `opencode` / `claude`：
  - 通过通用 JSON layer composer 生成 session-local 配置
  - 使用 `ui_shell_default.json` + runtime overrides + `ui_shell_enforced.json`

## Provider Refactor

`engine_shell_capability_provider.py` 只保留：

- 少量 probe / auth hint / runtime override strategy registry
- 基于 profile 构建 capability
- 基于 profile 的 config assets 生成 session-local 配置

不再手写每个 engine 的完整 JSON payload。
