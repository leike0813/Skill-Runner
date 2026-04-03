# claude-bootstrap-sandbox-availability-gating Design

## Design Overview

本次 change 只作用于 Claude headless 常规执行链路。实现分为三层：

1. bootstrap 期 smoke probe
2. Claude sandbox sidecar 持久化与读取
3. headless settings / prompt 基于 sidecar 做 gating

`ui_shell` 保持现有独立逻辑，不读取这份 sidecar。

## Bootstrap Probe

服务启动时 `main.lifespan()` 会先调用 `AgentCliManager.ensure_layout()`。本次在 Claude bootstrap sidecar 阶段执行一次 probe：

- 先检查 `bwrap` / `bubblewrap` 与 `socat` 是否存在
- 依赖齐全后执行短超时 `bubblewrap_smoke`
- smoke probe 使用与 runtime 一致的 PATH/env 解析
- 返回码为 `0` 视为 available
- `RTM_NEWADDR`、`creating new namespace failed`、`Operation not permitted`、timeout 等都视为 runtime unavailable

probe 采用 fail-open：不可用时只影响 Claude sandbox enablement，不阻止 run。

## Sidecar Contract

Claude bootstrap probe 结果写入：

- `agent_home/.claude/sandbox_probe.json`

sidecar 至少包含：

- `declared_enabled`
- `available`
- `status`
- `warning_code`
- `message`
- `dependencies`
- `missing_dependencies`
- `checked_at`
- `probe_kind`

这份 sidecar 是 Claude headless sandbox gating 的唯一真相源。服务运行期间不做按 run 重探测。

## Headless Config Gating

Claude config composer 在生成 run-local `settings.json` 时读取 bootstrap sidecar：

- `available = true`：保持现有 sandbox 设置与 run-local `allowWrite/denyWrite`
- `available = false`：强制把最终 `sandbox.enabled` 设为 `false`

其他 sandbox 字段继续保留，以便 sidecar 恢复为 available 后仍保持既有策略形状。

## Prompt Alignment

Claude 默认 prompt 需要与 bootstrap probe 结果一致：

- sandbox available：继续提示 “Prefer Bash inside the sandbox first”
- sandbox unavailable：改为明确告知当前环境 sandbox unavailable，直接正常执行 Bash，不要先走 sandbox-first retry 流程

这部分只作用于 Claude 默认模板与 fallback inline 文案。

## Observability

`collect_sandbox_status("claude")` 从“依赖存在检查”升级为读取 bootstrap sidecar：

- 可用时展示真实 probe success
- 不可用时展示 runtime unavailable / dependency missing
- sidecar 缺失时仅返回 unknown，不在 UI 路径上重新 probe
