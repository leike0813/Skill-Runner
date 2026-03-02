## Why

当前鉴权会话会在 `data/engine_auth_sessions/*` 持久化落盘 `events.jsonl`/`http_trace.log`/`pty.log` 等日志。该日志在日常运行中的长期价值有限，同时存在记录敏感信息（URL、code、token 线索）的风险，需要调整为安全优先策略。

## What Changes

- 将引擎鉴权会话日志持久化策略改为默认关闭（no-file persistence by default）。
- 新增显式开关用于按需启用鉴权会话落盘日志（仅用于受控调试场景）。
- 保留鉴权会话状态机与 API 可观测字段，不改变会话生命周期语义。
- 更新重置脚本与文档，明确 `engine_auth_sessions` 为可选清理项与安全注意事项。

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `engine-auth-observability`: 调整鉴权日志持久化语义，默认关闭落盘，仅在显式启用时按原目录结构写入。

## Impact

- Affected code:
  - `server/services/engine_management/engine_auth_flow_manager.py`
  - `server/runtime/auth/log_writer.py`
  - `server/core_config.py`
  - `scripts/reset_project_data.py`
  - `docs/containerization.md`
  - `docs/dev_guide.md`
  - 相关 engine auth 单元测试
- Public API:
  - HTTP API: no change
  - runtime schema/invariants: no change
- Behavior:
  - 默认不再创建/写入 `data/engine_auth_sessions/**`
  - 显式启用后继续沿用原有目录结构与文件命名
