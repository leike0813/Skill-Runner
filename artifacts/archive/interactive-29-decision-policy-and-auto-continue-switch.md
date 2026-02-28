# interactive-29-decision-policy-and-auto-continue-switch 实现记录

## 变更范围
- 交互决策协议升级：
  - `server/models.py` 将 `InteractionKind` 升级为 `choose_one/confirm/fill_fields/open_text/risk_ack`。
  - `AdapterTurnInteraction` / `PendingInteraction` 新增 `ui_hints`、`default_decision_policy`。
  - `server/adapters/base.py` 增加旧 kind 到新枚举的兼容映射与统一归一化。
- strict 开关落地：
  - `server/assets/configs/options_policy.json` 与 `server/services/options_policy.py` 新增 `interactive_require_user_reply`（interactive 默认 `true`）。
  - 新增布尔校验与默认注入逻辑。
- 编排行为矩阵实现：
  - `server/services/job_orchestrator.py` 新增 strict 解析、超时自动决策路径、自动回复续跑逻辑。
  - `strict=true` 保持既有行为：resumable 不自动推进、sticky 超时失败。
  - `strict=false` 新行为：resumable 自动 resume，sticky 自动注入继续执行。
- 审计与可观测：
  - 交互回复历史新增 `resolution_mode/resolved_at/auto_decide_reason/auto_decide_policy`。
  - `server/services/run_store.py` 新增 `get_auto_decision_stats`。
  - `server/routers/jobs.py` 与 `server/routers/management.py` 状态返回新增 `auto_decision_count`、`last_auto_decision_at`。
- Skill patch 策略：
  - `server/services/skill_patcher.py` interactive patch 改为约束 `kind/prompt` 与可选 `options/ui_hints/default_decision_policy`，明确用户回复可自由文本。
- 文档：
  - `docs/api_reference.md` 更新决策协议字段、kind 枚举、strict 开关说明、状态审计字段。
  - `docs/dev_guide.md` 更新 strict 行为矩阵与管理态审计字段说明。
- 测试：
  - 更新并新增 `tests/unit/test_options_policy.py`、`tests/unit/test_skill_patcher.py`、`tests/unit/test_run_store.py`、`tests/unit/test_jobs_interaction_routes.py`、`tests/unit/test_job_orchestrator.py`、`tests/unit/test_management_routes.py`、适配器相关测试。

## 测试与校验
- 相关子集回归：
  - `92 passed`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m pytest tests/unit/test_options_policy.py tests/unit/test_skill_patcher.py tests/unit/test_run_store.py tests/unit/test_jobs_interaction_routes.py tests/unit/test_job_orchestrator.py tests/unit/test_codex_adapter.py tests/unit/test_gemini_adapter.py tests/unit/test_iflow_adapter.py tests/unit/test_management_routes.py -q`
- 全量单元测试：
  - `330 passed`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m pytest tests/unit -q`
- 类型检查：
  - `Success: no issues found in 52 source files`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m mypy server`
- OpenSpec：
  - `openspec validate interactive-29-decision-policy-and-auto-continue-switch --type change --strict`
  - `openspec archive interactive-29-decision-policy-and-auto-continue-switch -y`
  - 归档目录：`openspec/changes/archive/2026-02-16-interactive-29-decision-policy-and-auto-continue-switch`
  - 同步 spec：
    - `openspec/specs/interactive-decision-policy/spec.md`
    - `openspec/specs/interactive-job-api/spec.md`
    - `openspec/specs/interactive-run-lifecycle/spec.md`
    - `openspec/specs/interactive-session-timeout-unification/spec.md`
