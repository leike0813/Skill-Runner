# claude-sandbox-policy-relaxation-and-fallback Design

## Design Overview

本次 change 只作用于 Claude headless / harness 运行链路。实现由三部分组成：

1. Claude headless settings policy 放宽
2. Claude 默认 prompt 增加 fallback 使用规则
3. Claude sandbox diagnostics 细化分类

`ui_shell` 继续使用独立配置，不共享这次策略放宽。

## Headless Sandbox Policy

Claude headless enforced config 保持：

- `sandbox.enabled = true`
- `sandbox.autoAllowBashIfSandboxed = true`

并改为：

- `sandbox.allowUnsandboxedCommands = true`
- `sandbox.filesystem.allowWrite` 默认包含 `/tmp`

Claude dynamic enforced config 继续只负责 run-scope 限写：

- 允许写 `run_dir`
- 禁止写 `agent_home`
- 当项目根不在当前 run 根内时，继续禁止写项目根

由于当前 JSON config generator 会覆盖数组字段，Claude config composer 需要在 compose 阶段为 sandbox 列表字段做定向合并，确保：

- enforced `/tmp` 不会被 dynamic `run_dir` 覆盖
- `options["claude_config"]` 与 skill defaults 中的 sandbox list 配置仍可叠加

## Prompt Fallback Guidance

Claude 默认 prompt 需要明确以下行为：

- 默认优先在 sandbox 内执行 Bash
- 若遇到已知 sandbox 基础设施失败，可重试一次 unsandboxed fallback
- 仅允许以下失败触发 fallback：
  - `bwrap` / `bubblewrap` / `socat` 缺失
  - `Failed RTM_NEWADDR`
  - `creating new namespace failed`
  - 等价 sandbox 启动级失败
- 不得将普通策略拒绝升级为 unsandboxed fallback：
  - 非 allowlist 域名访问
  - 越界写系统路径
  - 访问敏感目录

这部分只通过默认 prompt / fallback inline 注入，不新增 runtime retry 机制。

## Sandbox Diagnostics

Claude parser diagnostics 继续保持 warning-only，但从泛化 code 细化为三类：

- `CLAUDE_SANDBOX_DEPENDENCY_MISSING`
- `CLAUDE_SANDBOX_RUNTIME_FAILURE`
- `CLAUDE_SANDBOX_POLICY_VIOLATION`

分类规则：

- 依赖缺失：`bwrap` / `bubblewrap` / `socat` 缺失或 not found
- 运行时失败：`RTM_NEWADDR`、namespace 创建失败、bubblewrap runtime error
- 策略拦截：命令已进入执行，但被沙箱策略拒绝，例如越界写、敏感路径访问、显式 sandbox policy block

已知 runtime failure 不得再重复归类为 policy violation。

## Schema Alignment

本次不依赖 `filesystem.allowRead`。虽然 Anthropic 文档提到该字段，但当前 vendored Claude schema 不支持它；由于现有 config generation 使用真实 JSON Schema 校验，直接引入会导致配置生成失败。
