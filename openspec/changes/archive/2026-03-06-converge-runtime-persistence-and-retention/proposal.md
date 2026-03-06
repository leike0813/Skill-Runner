# Change: converge-runtime-persistence-and-retention

## Why
- 运行时持久化仍存在多轨：`runs.db`、`skill_installs.db`、`runtime_process_leases/*.json`、已退役 temp 链路数据库/目录。
- 清理策略只覆盖 runs 主体，`tmp_uploads`/`ui_shell_sessions`/closed leases 缺少统一周期回收。
- 测试存在写入部署数据目录风险，导致本地环境污染和排障噪声。

## What
- 将 `process_leases` 与 `skill_installs` 收敛到 `runs.db`（同库分表）。
- 硬切删除 `temp_skill_runs` 旧路由/旧 store，停止 `temp_skill_runs.db` 触发源。
- 将 temp skill 上传暂存统一到 `data/tmp_uploads/<request_id>`，并接入即时 + 周期清理。
- 将 `ui_shell_sessions` 纳入周期清理，复用 `RUN_RETENTION_DAYS` 与 `RUN_CLEANUP_INTERVAL_HOURS`。
- 测试环境强制使用独立临时数据根，禁止写入仓库 `data/`。
- 同步 `data reset` 服务与脚本到新的持久化真相源。

## Impact
- 对外 API 不新增路径；`/v1/temp-skill-runs/*` 维持下线（404）。
- 运行行为不变，主要变更为持久化后端与清理策略收敛。
