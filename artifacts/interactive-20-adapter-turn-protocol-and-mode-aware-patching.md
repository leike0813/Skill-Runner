# interactive-20-adapter-turn-protocol-and-mode-aware-patching 实现记录

## 变更范围
- 统一回合协议：
  - `server/models.py` 新增 `AdapterTurnOutcome`、`AdapterTurnInteraction`、`AdapterTurnResult`。
  - `server/adapters/base.py` 引入回合级解析契约：
    - 将 adapter 输出统一归一到 `final / ask_user / error`。
    - 增加 ask_user 载荷严格校验（`interaction_id`、`prompt` 等）。
    - 保持兼容：普通 JSON 仍按 `final_data` 处理。
- 三引擎适配升级：
  - `server/adapters/codex_adapter.py`
  - `server/adapters/gemini_adapter.py`
  - `server/adapters/iflow_adapter.py`
  - 三引擎 `_parse_output` 均改为返回统一回合结果，并支持 ask_user envelope 判定。
  - 命令构造按 `execution_mode` 分支：
    - `auto`：保留自动执行参数（Codex=`--full-auto|--yolo`，Gemini/iFlow=`--yolo`）。
    - `interactive`：移除自动执行参数。
    - `resume`：不注入自动执行参数。
- 运行时 patch 策略拆分：
  - `server/services/skill_patcher.py` 增加 `execution_mode` 入参。
  - 拆分为 `artifact_patch` 与 `mode_patch`，固定顺序 `artifact_patch -> mode_patch`。
  - `interactive` 文案允许 ask_user 且要求结构化 interaction。
- 交互校验补强：
  - `server/services/job_orchestrator.py` 增加“看起来是 ask_user 但载荷无效”的失败分支，避免误进入成功态。

## 测试与校验
- 定向单测：
  - `54 passed`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m pytest tests/unit/test_adapter_parsing.py tests/unit/test_codex_adapter.py tests/unit/test_gemini_adapter.py tests/unit/test_iflow_adapter.py tests/unit/test_skill_patcher.py tests/unit/test_adapter_failfast.py tests/unit/test_job_orchestrator.py -q`
- 全量单元测试：
  - `289 passed`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m pytest tests/unit`
- 类型检查：
  - `Success: no issues found in 51 source files`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m mypy server`
- OpenSpec：
  - `openspec validate interactive-20-adapter-turn-protocol-and-mode-aware-patching --type change --strict --no-interactive`
  - `openspec archive interactive-20-adapter-turn-protocol-and-mode-aware-patching -y`
  - 归档目录：`openspec/changes/archive/2026-02-16-interactive-20-adapter-turn-protocol-and-mode-aware-patching`
