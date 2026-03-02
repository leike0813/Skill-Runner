## 1. OpenSpec Artifacts

- [x] 1.1 创建 `proposal.md`，明确 models god-file 拆分目标与边界
- [x] 1.2 创建 `specs/models-module-boundary/spec.md`
- [x] 1.3 创建 `design.md`，固化分域拆分与兼容策略

## 2. Model Module Split

- [x] 2.1 新增分域模型模块：
  - `server/models_common.py`
  - `server/models_run.py`
  - `server/models_skill.py`
  - `server/models_engine.py`
  - `server/models_interaction.py`
  - `server/models_management.py`
  - `server/models_runtime_event.py`
  - `server/models_error.py`
- [x] 2.2 将 `server/models.py` 的模型定义按域迁移到对应新模块
- [x] 2.3 将 `server/models.py` 收敛为兼容聚合层（re-export）

## 3. Import and Validation

- [x] 3.1 校验现有 `from server.models import ...` 调用路径保持可用
- [x] 3.2 在必要处（内部同域）按新模块进行局部导入优化（可选，不改变外部导入，本轮无必要新增改动）
- [x] 3.3 新增结构守卫测试（如 `tests/unit/test_models_module_structure.py`）
- [x] 3.4 新增导出完整性测试（关键模型/枚举可导入）

## 4. Regression and Type Checks

- [x] 4.1 运行关键回归测试：
  - `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_runtime_event_protocol.py tests/unit/test_run_observability.py tests/unit/test_management_routes.py tests/unit/test_jobs_interaction_routes.py`
- [x] 4.2 运行模型与编排相关测试：
  - `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_job_orchestrator.py tests/unit/test_workspace_manager.py tests/unit/test_schema_validator.py`
- [x] 4.3 运行类型检查：
  - `conda run --no-capture-output -n DataProcessing python -u -m mypy --follow-imports=skip server/models.py server/models_common.py server/models_run.py server/models_skill.py server/models_engine.py server/models_interaction.py server/models_management.py server/models_runtime_event.py server/models_error.py`
