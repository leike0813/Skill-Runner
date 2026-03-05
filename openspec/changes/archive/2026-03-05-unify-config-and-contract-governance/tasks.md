## 1. Config Governance Foundation

- [x] 1.1 新增 `server/config_registry/{keys,registry,loaders}.py` 统一配置读取入口。
- [x] 1.2 为 engine config / contracts schema / invariants 提供 canonical + legacy 回退路径。

## 2. YACS Concurrency Canonicalization

- [x] 2.1 在 `server/core_config.py` 新增 `SYSTEM.CONCURRENCY.*`。
- [x] 2.2 `concurrency_manager` 移除 JSON policy 文件依赖，改读 YACS。
- [x] 2.3 更新并发相关单测到 YACS 路径。

## 3. Engine Capability Migration (Phase-1)

- [x] 3.1 新增 `server/engines/*/config/command_profile.json`。
- [x] 3.2 新增 `server/engines/*/config/auth_strategy.yaml`。
- [x] 3.3 改造 `engine_command_profile` 与 `engine_auth_strategy_service` 为按 engine 聚合读取。

## 4. Contract Canonical Path (Phase-1)

- [x] 4.1 新增 `server/contracts/schemas/engine_auth_strategy.schema.json`。
- [x] 4.2 新增/收敛 `server/contracts/{schemas,invariants}` 契约文件（`ask_user` 位于 schemas）。
- [x] 4.3 改造 `schema_registry`、`profile_loader`、`skill_patcher` 为新路径优先读取。

## 5. Docs & Validation

- [x] 5.1 更新关键文档中的契约路径引用。
- [x] 5.2 跑相关单测并修正失败。
- [x] 5.3 扩展 phase-2 清理与 CI 守卫。
