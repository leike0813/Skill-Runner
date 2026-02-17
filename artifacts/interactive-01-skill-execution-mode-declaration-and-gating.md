# interactive-01 实现记录

## 变更目标
- 在 `runner.json` 增加并强校验 `execution_modes`
- 在 Jobs 与 Temp Skill Run 提交流程做执行模式准入
- 对存量已安装且缺失声明的 skill 做 `["auto"]` 兼容映射并告警

## 主要实现
- `SkillManifest` 新增 `execution_modes` 字段，枚举为 `auto|interactive`
- `SkillRegistry` 对缺失 `execution_modes` 的已安装 skill 自动回退为 `["auto"]`，并输出 deprecation warning
- `SkillPackageValidator` 新增统一 `execution_modes` 校验逻辑（安装与临时上传共用）
- `POST /v1/jobs` 增加模式准入校验；不支持时返回：
  - HTTP 400
  - `code=SKILL_EXECUTION_MODE_UNSUPPORTED`
- `POST /v1/temp-skill-runs/{request_id}/upload` 增加同样的模式准入校验和错误语义

## 测试与类型检查
- 全量单元测试：
  - `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit -q`
  - 结果：`245 passed`
- 类型检查：
  - `conda run --no-capture-output -n DataProcessing python -u -m mypy server`
  - 结果：`Success: no issues found in 50 source files`

## OpenSpec 验证与归档
- 验证：
  - `openspec validate "interactive-01-skill-execution-mode-declaration-and-gating" --type change --strict --no-interactive`
  - 结果：`valid`
- 归档：
  - `openspec archive "interactive-01-skill-execution-mode-declaration-and-gating" -y`
  - 归档目录：`openspec/changes/archive/2026-02-16-interactive-01-skill-execution-mode-declaration-and-gating`
  - 同步规格：
    - `openspec/specs/ephemeral-skill-validation/spec.md`
    - `openspec/specs/interactive-job-api/spec.md`
    - `openspec/specs/skill-execution-mode-declaration/spec.md`
    - `openspec/specs/skill-package-install/spec.md`
