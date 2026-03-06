# Design

## 1. Persistence Convergence

### 1.1 process leases
- `ProcessLeaseStore` 改为 `runs.db` 上的 `process_leases` 表实现。
- 保持接口兼容：`upsert_active/get/close/list_active`，新增 `prune_closed_before` 用于周期回收。
- `RuntimeProcessSupervisor` 无需改调用语义，仅切换存储后端。

### 1.2 skill installs
- `SkillInstallStore` 默认数据库切到 `runs.db`（`skill_installs` 表）。
- 保留 legacy `SKILL_INSTALLS_DB` 仅用于一次性迁移读取，不再作为运行时真源。

## 2. Temp Legacy Hard Cut
- 删除 `server/routers/temp_skill_runs.py` 与 `server/services/skill/temp_skill_run_store.py`。
- `run_source_adapter` 删除 temp source 分支，保留 installed 单路。
- `temp_skill_run_manager` 收敛为“仅做 temp package 检查”的轻量服务，不再维护 temp request 生命周期。

## 3. Upload Staging and Retention
- `/v1/jobs/{request_id}/upload` staging 改到 `SYSTEM.TMP_UPLOADS_DIR/request_id/uploads`。
- 上传链路结束后（成功/失败）执行 best-effort 目录删除。
- `RunCleanupManager` 增加辅助清理：
  - 清理过期 `tmp_uploads/*`
  - 清理过期 `ui_shell_sessions/*`（排除 active lease 对应目录）
  - 清理 `process_leases` 中 closed 且超 retention 的记录

## 4. Data Reset Alignment
- `DataResetService` 的 DB 目标改为：
  - `runs.db`
  - `engine_upgrades.db`
- 删除对 `skill_installs.db`、`runtime_process_leases` 的目标依赖。
- 可选路径加入 `tmp_uploads`；重建目录加入 `TMP_UPLOADS_DIR`。

## 5. Test Isolation Guard
- `tests/conftest.py` 增加 autouse fixture：
  - 每个测试将 `SYSTEM.DATA_DIR` 与关键路径重定向到 `tmp_path`。
  - `SKILL_INSTALLS_DB` 指向 `RUNS_DB`，防止生成独立安装库。
  - 保留旧键仅作为兼容字段，不影响真实落盘后端。
