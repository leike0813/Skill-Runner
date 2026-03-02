## 1. OpenSpec Artifacts

- [x] 1.1 创建 `proposal.md` 并固化迁移动机与边界
- [x] 1.2 创建 `specs/engine-management-domain-boundary/spec.md`（完整 Spec）
- [x] 1.3 创建 `design.md` 并固化目录划分与风险控制

## 2. Engine Management Package Migration

- [x] 2.1 新增 `server/services/engine_management/__init__.py`
- [x] 2.2 迁移 11 个 engine 管理模块到 `server/services/engine_management/`
- [x] 2.3 删除 `server/services/orchestration/` 下对应旧模块（无兼容壳）

## 3. Import Cutover

- [x] 3.1 更新 orchestration 侧导入（`job_orchestrator.py`、`run_execution_core.py`、`workspace_manager.py`、`runtime_protocol_ports.py`、`run_folder_trust_manager.py`）
- [x] 3.2 更新 router 侧导入（`engines.py`、`ui.py`、`management.py`、`jobs.py`、`temp_skill_runs.py`、`oauth_callback.py`）
- [x] 3.3 更新 engines/skill/ui 服务侧导入
- [x] 3.4 更新 tests 的 import/monkeypatch/路径断言到新路径

## 4. Docs and Verification

- [x] 4.1 更新 `docs/core_components.md`
- [x] 4.2 更新 `docs/project_structure.md`
- [x] 4.3 运行旧路径残留扫描并确认为 0
- [x] 4.4 运行 engine 管理相关单测
- [x] 4.5 运行路由回归测试
- [x] 4.6 运行编排与运行回归测试
- [x] 4.7 运行 mypy（`server/services/engine_management` 与关键 orchestration 模块）
