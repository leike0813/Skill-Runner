# ui-shell-security-governance-unification Proposal

## Summary

统一 `ui_shell` 的安全配置治理来源：

- 能用 adapter profile 表达的，一律放进 profile
- profile 表达不了的，再落到 engine 专用 `ui_shell` 配置资产
- 不再在 `engine_shell_capability_provider.py` 里手写各引擎的大段 session 安全配置 JSON

## Motivation

当前 `ui_shell` 的安全治理来源混杂：

- 一部分限制在 `command_defaults.ui_shell`
- 一部分限制写死在 `engine_shell_capability_provider.py`

这让安全策略来源不统一，也让新增/维护 engine 时继续把策略散落进 Python 代码的风险变高。

## Scope

- 扩展 adapter profile 的 `ui_shell` 元数据
- 为 `gemini` / `iflow` / `opencode` / `claude` 提供 `ui_shell` 配置资产
- 将 capability provider 改成 metadata-driven

## Non-Goals

- 不重设计各 engine 的 `ui_shell` 安全姿态
- 不合并 `ui_shell` 与 headless run 的策略
- 不改变对外 HTTP API
