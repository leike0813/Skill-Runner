# claude-sandbox-policy-relaxation-and-fallback Proposal

## Summary

优化 Claude headless / harness 执行链路的 sandbox 策略：继续默认开启 sandbox，但不再维持过于严格的 fail-closed Bash 策略；对已知 sandbox 基础设施失败允许受控的 unsandboxed fallback，同时保持 `ui_shell` 的现有严格姿态不变。

## Motivation

当前 Claude headless 配置将：

- `sandbox.enabled = true`
- `sandbox.autoAllowBashIfSandboxed = true`
- `sandbox.allowUnsandboxedCommands = false`

与 run-local `denyWrite` 组合在一起，形成了非常保守的策略。它能保护系统，但在 Linux `bubblewrap` / namespace 兼容性不稳定时，Claude 很容易把原本可继续完成的 Bash 工作流完全压成不可用状态。

Anthropic 的 sandbox 文档明确支持：

- 在 sandbox 内优先执行 Bash
- 通过 `filesystem.allowWrite` 等配置为常规子进程提供受控放宽
- 在必要时允许 unsandboxed fallback，而不是把所有失败都视为策略拒绝

本次 change 目标是改善 headless 常规工作流的可用性，而不是削弱 `ui_shell` 或默认关闭 sandbox。

## Scope

- 调整 Claude headless enforced sandbox policy
- 保持 run-local 动态限写，同时放宽常规临时写路径
- 给 Claude 默认 prompt 增加 sandbox fallback 使用约束
- 细化 Claude sandbox diagnostics，区分依赖缺失、运行时失败、策略拦截
- 创建对应 OpenSpec delta spec 与回归测试

## Non-Goals

- 不修改 Claude `ui_shell` 的 restrictive security posture
- 不引入 adapter 级整次 run 自动 retry-without-sandbox
- 不默认启用 `enableWeakerNestedSandbox`
- 不通过宽泛 `excludedCommands` 将 sandbox 架空
- 不引入 `filesystem.allowRead`，直到 vendored schema 与官方文档重新对齐

## Capabilities

### Modified Capabilities

- `engine-adapter-runtime-contract`
