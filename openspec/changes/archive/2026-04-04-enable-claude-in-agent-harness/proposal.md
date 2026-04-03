## Why

`agent_harness` 仍维护一份独立的 supported engine 白名单，导致已经接入主系统的 `claude` 仍被 harness 拒绝为 `ENGINE_UNSUPPORTED`。这让 harness 与主服务的 engine 能力集合发生漂移，也阻断了 Claude 的本地调试和回归验证链路。

## What Changes

- 让 `agent_harness` 接受 `claude` 作为合法 engine
- 保持 harness 继续复用现有 Claude adapter 的 `start` / `resume` / runtime parse 合同
- 补齐 harness runtime 与 CLI 的 Claude 回归测试
- 不新增 Claude 专属 harness 命令拼接或专属配置注入逻辑

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- `external-runtime-harness-cli`: harness CLI 支持 `claude` 作为合法 engine 标识
- `harness-shared-adapter-execution`: harness 对 `claude` 继续走共享 adapter 命令构建与恢复路径

## Impact

- Affected code:
  - `agent_harness/runtime.py`
  - `tests/unit/test_agent_harness_runtime.py`
  - `tests/unit/test_agent_harness_cli.py`
- No public HTTP API changes
- CLI behavior change:
  - `agent-harness start claude ...`
  - `agent-harness claude ...`
  become valid calls
