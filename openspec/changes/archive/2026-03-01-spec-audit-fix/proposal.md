## Why

通过系统审计发现 51 个 OpenSpec spec 中存在路径过时、键名不一致、Purpose 缺失（75%）等问题。本 change 以 delta spec 方式统一修正，保证改动历史可追溯。

> **本次 change 仅做 spec 对齐，不修改任何代码文件。**

## What Changes

**P0 — 关键修正**
- `run-log-streaming`：日志路径从 `logs/stdout.txt` 更新为 `.audit/stdout.<N>.log`
- `interactive-session-timeout-unification`：统一超时键为 `interactive_reply_timeout_sec`

**P1 — 状态标注**
- `engine-oauth-proxy-feasibility`：标记 DEPRECATED（可行性阶段已过，结论已融入 `engine-auth-observability`）
- `web-client-management-api-adapter`：标记 DEFERRED（当前 Management UI 为 SSR 实现）

**P2 — 质量提升**
- `interactive-run-cancel-lifecycle`：补充进程信号升级策略和 session handle 清理语义
- 38 个 TBD Purpose spec：批量补写 Purpose 描述

## Capabilities

### New Capabilities
_无。_

### Modified Capabilities
- `run-log-streaming`: 路径引用更新为 `.audit/` attempt 分区布局
- `interactive-session-timeout-unification`: 超时键从 `session_timeout_sec` 更新为 `interactive_reply_timeout_sec`
- `interactive-decision-policy`: 补写 Purpose
- `engine-oauth-proxy-feasibility`: 标记 DEPRECATED，注明后续跟踪在 `engine-auth-observability`
- `web-client-management-api-adapter`: 标记 DEFERRED，补写 Purpose 说明 SSR 现状
- `interactive-run-cancel-lifecycle`: 补充信号升级与 handle 清理 requirements
- `builtin-e2e-example-client`: 补写 Purpose
- `engine-auth-observability`: 补写 Purpose
- `engine-command-profile-defaults`: 补写 Purpose
- `engine-execution-failfast`: 补写 Purpose
- `engine-hard-timeout-policy`: 补写 Purpose
- `engine-runtime-config-layering`: 补写 Purpose
- `ephemeral-skill-lifecycle`: 补写 Purpose
- `ephemeral-skill-upload-and-run`: 补写 Purpose
- `ephemeral-skill-validation`: 补写 Purpose
- `external-runtime-harness-audit-translation`: 补写 Purpose
- `external-runtime-harness-cli`: 补写 Purpose
- `external-runtime-harness-environment-paths`: 补写 Purpose
- `external-runtime-harness-test-adoption`: 补写 Purpose
- `harness-shared-adapter-execution`: 补写 Purpose
- `interactive-engine-turn-protocol`: 补写 Purpose
- `interactive-job-api`: 补写 Purpose
- `interactive-job-cancel-api`: 补写 Purpose
- `interactive-run-observability`: 补写 Purpose
- `local-deploy-bootstrap`: 补写 Purpose
- `management-api-surface`: 补写 Purpose
- `mixed-input-protocol`: 补写 Purpose
- `output-json-repair`: 补写 Purpose
- `run-folder-trust-lifecycle`: 补写 Purpose
- `run-observability-ui`: 补写 Purpose
- `runtime-environment-parity`: 补写 Purpose
- `skill-converter-agent`: 补写 Purpose
- `skill-converter-directory-first`: 补写 Purpose
- `skill-converter-dual-mode`: 补写 Purpose
- `skill-converter-prompt-first`: 补写 Purpose
- `skill-execution-mode-declaration`: 补写 Purpose
- `skill-package-archive`: 补写 Purpose
- `skill-package-install`: 补写 Purpose
- `skill-package-validation-schema`: 补写 Purpose
- `trust-config-bootstrap`: 补写 Purpose
- `ui-auth-hardening`: 补写 Purpose

## Impact

- **代码**: 无源码变更
- **Spec**: 44 个 spec 将通过 delta spec 方式修订
- **风险**: 极低（spec 层面对齐，不影响运行时行为）
