## Context

治理目标是“保留 YACS、不改业务语义”的前提下，完成配置与契约路径收口。

## Decisions

1. YACS 继续作为系统配置容器；并发策略收敛到 `config.SYSTEM.CONCURRENCY.*`。
2. 引擎能力配置按 engine 分文件管理，由聚合服务输出统一视图。
3. 契约 canonical 路径迁到 `server/contracts`，phase-1 允许旧路径回退。
4. 读取入口统一：业务层不再直接拼路径读 policy/contract。

## Architecture

### Config Registry / Loaders

- `server/config_registry/registry.py`
- `server/config_registry/loaders.py`
- `server/config_registry/keys.py`

职责：

- 维护 canonical 路径和 phase-1 兼容回退路径。
- 提供 JSON/YAML 统一加载与错误语义。

### Concurrency Policy

- `server/core_config.py` 新增 `SYSTEM.CONCURRENCY.*` 默认值。
- `server/services/platform/concurrency_manager.py` 改为读取 YACS + env override。

### Engine Capability Aggregation

- `engine_command_profile`：优先读取 `server/engines/<engine>/config/command_profile.json`，缺失回退 legacy。
- `engine_auth_strategy_service`：按 engine 聚合 `auth_strategy.yaml`，缺失回退 legacy 全局策略。

### Contract Resolution

- `schema_registry`、`profile_loader`、`skill_patcher` 改为新路径优先、旧路径回退。

## Migration Plan

### Phase 1 (this change)

- 完成新路径落地与读取入口切换。
- 保持 legacy fallback，保证行为兼容。

### Phase 2 (follow-up)

- 删除旧路径文件与 fallback。
- 增加 CI 守卫（禁止 legacy path 与 direct file read）。
