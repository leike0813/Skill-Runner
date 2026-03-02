## Context

现有实现通过 `AuthLogWriter` 在 `data/engine_auth_sessions/<transport>/<session_id>/` 写入鉴权会话日志。该机制最初用于链路排查，但在常态运行中会产生敏感信息落盘风险，且运营收益有限。

## Goals / Non-Goals

**Goals**
- 将鉴权会话文件日志改为默认关闭。
- 保留按需调试能力：显式开关开启后维持现有目录/文件兼容。
- 保持鉴权会话状态机、API 字段、UI 交互语义不回归。

**Non-Goals**
- 不重写鉴权状态机。
- 不变更 HTTP API 结构。
- 不改 run/audit 等其他日志域策略。

## Decisions

### 1) 引入显式持久化开关
- Decision: 新增 `SYSTEM.ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED`（env 覆盖：`ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED`，默认 `false`）。
- Rationale: 将敏感落盘从默认行为改为“显式 opt-in”。

### 2) 日志写入降级为 no-op writer
- Decision: 在 `EngineAuthFlowManager` 初始化时按开关选择 writer：
  - 开启：`AuthLogWriter`（现有行为）
  - 关闭：`NoopAuthLogWriter`（不创建目录，不写文件）
- Rationale: 最小改动保留现有调用点，避免在业务流程里加大量条件分支。

### 3) 快照字段兼容
- Decision: 日志关闭时 `log_root` 可为 `null` 或未创建路径，但状态/挑战字段保持原语义。
- Rationale: 避免前端或 API 消费方因无日志目录而误判会话失败。

### 4) 清理脚本保持“可选清理”
- Decision: `scripts/reset_project_data.py` 继续保留 `--include-engine-auth-sessions` 可选项，不改为默认清理。
- Rationale: 兼容已存在历史数据与受控审计场景。

## Risks / Trade-offs

- [Risk] 关闭默认落盘后，线上排障细节减少。
  - Mitigation: 保留显式开关与文档说明，故障期可短时启用。
- [Risk] 既有测试依赖目录存在。
  - Mitigation: 更新相关单测，区分默认关闭与显式开启两条路径。

## Migration Plan

1. `core_config` 新增开关并支持环境变量覆盖。
2. 新增 `NoopAuthLogWriter` 并在 flow manager 注入。
3. 更新 engine auth 相关测试：默认不落盘 + 显式开启落盘。
4. 更新文档与安全说明，标注持久化日志为调试专用。
5. 回归 engine auth 相关测试与路由测试。

## Open Questions

- 无。方案已锁定为“默认关闭 + 显式开关启用 + 行为兼容”。
