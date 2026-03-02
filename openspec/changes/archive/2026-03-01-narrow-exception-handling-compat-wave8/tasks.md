## 1. Baseline Freeze and Residual Matrix

- [x] 1.1 固定 wave8 起点基线（`server/` broad catch total=52）并记录全量残余文件分布
- [x] 1.2 建立残余分组矩阵（`pass/loop/return/other/log`）并逐条标注可收窄或受控保留
- [x] 1.3 明确保留项的结构化诊断落点（`component/action/error_type/fallback`）与兼容注释要求

## 2. Wave A — Swallow-style Closeout (High Priority)

- [x] 2.1 清理 auth driver 与 config 路径中的 `pass/return` broad catch（gemini/iflow/opencode/codex config composer）
- [x] 2.2 清理 orchestration/runtime 中 `loop/return/other` broad catch（run_interaction_lifecycle_service、run_read_facade、runtime/session timeout、runtime/auth session_lifecycle）
- [x] 2.3 清理 router/platform/skill 中 `other/return` broad catch（skill_packages、oauth_callback、options_policy、run_interaction_service、run_audit_service）

## 3. Wave B — Log-style Residual Convergence

- [x] 3.1 对 `log` 型 broad catch 全量评估：可收窄则改为 typed catch
- [x] 3.2 对必须保留的 `log` 型 broad catch 补齐结构化诊断字段与兼容性注释
- [x] 3.3 覆盖剩余长尾模块（jobs/management/temp_skill_runs、engine_upgrade_manager、concurrency_manager、skill/temp run manager、catalog_service、skill_registry、ui_shell_manager 等）

## 4. Wave C — Final Allowlist Closeout

- [x] 4.1 更新 `docs/contracts/exception_handling_allowlist.yaml` 到 wave8 终态基线（只降不升）
- [x] 4.2 验证终态保留项均映射到 approved contexts 且可审计
- [x] 4.3 复核波次后残余 broad catch 是否仅为受控边界保留集合

## 5. Validation Gate

- [x] 5.1 运行 `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_no_unapproved_broad_exception.py`
- [x] 5.2 运行 auth/router/skill/platform 组合回归（按触达模块覆盖对应测试）
- [x] 5.3 若触达 runtime 行为，运行 AGENTS.md runtime 必跑清单
- [x] 5.4 对本波修改文件执行 `mypy`（优先 `--follow-imports=skip` 聚焦改动文件）
