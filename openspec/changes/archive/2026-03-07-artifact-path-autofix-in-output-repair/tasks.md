## 1. Artifact Path Autofix

- [x] 1.1 新增 orchestration helper：解析 output schema 的 artifact 字段映射并执行路径修复
- [x] 1.2 在 `run_job_lifecycle_service` 终态校验中接入 autofix 尝试
- [x] 1.3 autofix 后执行二次 artifact + schema 校验

## 2. Warning 与可观测性

- [x] 2.1 增加 `OUTPUT_ARTIFACT_PATH_REPAIRED` warning
- [x] 2.2 增加 `OUTPUT_ARTIFACT_PATH_REPAIR_TARGET_EXISTS` warning
- [x] 2.3 增加 `OUTPUT_ARTIFACT_PATH_REPAIR_OUTSIDE_RUN_DIR` warning

## 3. 测试

- [x] 3.1 新增“uploads -> artifacts 自动搬运成功”单测
- [x] 3.2 新增“目标已存在不覆盖且告警”单测
- [x] 3.3 新增“run_dir 外路径拒绝修复并失败”单测
- [x] 3.4 新增“修复后二次校验与输出路径回写”单测
- [x] 3.5 运行 `tests/unit/test_job_orchestrator.py` 回归
