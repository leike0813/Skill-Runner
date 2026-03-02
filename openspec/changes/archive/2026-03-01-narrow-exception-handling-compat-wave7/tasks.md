## 1. Baseline Freeze and Target Classification

- [x] 1.1 固定 wave7 起点基线（`server/` broad catch total=65）并记录目标文件分类分布
- [x] 1.2 逐条标注 `config_composer`、`toml_manager`、`skill_package_manager` 中可收窄与需保留分支（含兼容理由）
- [x] 1.3 确认保留 broad catch 的结构化诊断字段落点（`component/action/error_type/fallback`）

## 2. Wave A — Engine Config Composer Narrowing

- [x] 2.1 在 `server/engines/iflow/adapter/config_composer.py` 收窄 deterministic broad catch
- [x] 2.2 在 `server/engines/gemini/adapter/config_composer.py` 收窄 deterministic broad catch
- [x] 2.3 运行 `tests/unit/test_iflow_adapter.py tests/unit/test_gemini_adapter.py` 验证兼容

## 3. Wave B — Codex TOML Manager Narrowing

- [x] 3.1 在 `server/engines/codex/adapter/config/toml_manager.py` 收窄 TOML/文件处理 broad catch
- [x] 3.2 保持配置回退与写入语义不变并补齐必要诊断信息
- [x] 3.3 运行 `tests/unit/test_codex_config.py tests/unit/test_codex_config_fusion.py` 验证兼容

## 4. Wave C — Skill Package Manager Narrowing

- [x] 4.1 在 `server/services/skill/skill_package_manager.py` 收窄 deterministic broad catch
- [x] 4.2 保持 install/state 语义不变并补齐必要诊断信息
- [x] 4.3 运行 `tests/unit/test_skill_package_manager.py tests/unit/test_skill_packages_router.py` 验证兼容

## 5. Allowlist Ratchet and Validation Gate

- [x] 5.1 更新 `docs/contracts/exception_handling_allowlist.yaml` 到 wave7 新基线（只降不升）
- [x] 5.2 运行 `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_no_unapproved_broad_exception.py`
- [x] 5.3 运行 `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_iflow_adapter.py tests/unit/test_gemini_adapter.py tests/unit/test_codex_config.py tests/unit/test_codex_config_fusion.py tests/unit/test_skill_package_manager.py tests/unit/test_skill_packages_router.py`
