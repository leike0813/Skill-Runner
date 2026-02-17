## Why

当前 adapter 契约只返回“最终结果 JSON 或失败”，无法表达“当前需要用户补充信息”的中间语义。  
另外，`skill_patcher` 目前强制注入“不得向用户提问”，这与 interactive 模式目标冲突。

因此必须同步升级 adapter 协议与运行时 patch 策略。
此外，adapter 在调用 CLI 时当前默认带自动执行参数（如 `--yolo` / `--full-auto`）。  
interactive 模式下如果继续携带这些参数，会与“允许中途等待用户决策”目标冲突。

## Dependency

- 本 change 依赖 `interactive-05-engine-session-resume-compatibility`。
- adapter 的 ask/final 协议必须与 `interactive-05` 定义的会话句柄与 `interactive_profile(resumable|sticky_process)` 保持一致。

## What Changes

1. 定义统一的回合输出协议（Turn Protocol）：
   - `final`：产生最终结果；
   - `ask_user`：返回待决问题；
   - `error`：不可恢复失败。

2. 升级 `EngineAdapter` 抽象：
   - 从单次 `run()` 模型扩展到可用于多回合 orchestration 的协议返回。

3. 三引擎解析一致性：
   - Codex/Gemini/iFlow 均按统一 envelope 解析 ask/final。
   - 不允许各引擎私有格式直接外泄到 orchestrator。

4. `skill_patcher` 改为分步、模式感知：
   - 将 patch 拆分为两个步骤：
     - `artifact_patch`：只负责输出文件路径重定向（写入 `artifacts/`）；
     - `mode_patch`：只负责执行语义约束（是否允许 ask_user）。
   - `artifact_patch` 对 `auto`/`interactive` 均必须执行；
   - `mode_patch` 按 execution mode 区分：
     - `auto` 保留“不得询问用户”约束；
     - `interactive` 去除该硬约束，改为“可请求用户决策，但必须结构化提出问题”。

5. CLI 命令构造改为模式感知：
   - `auto`：
     - Gemini / iFlow 继续使用 `--yolo`；
     - Codex 继续沿用现有自动执行参数策略（`--full-auto` 或 `--yolo`）。
   - `interactive`：
     - Gemini / iFlow 不得注入 `--yolo`；
     - Codex 不得注入 `--full-auto` 或 `--yolo`；
     - 恢复回合（resume）同样不得注入自动执行参数。

## Impact

- `server/adapters/base.py`
- `server/adapters/codex_adapter.py`
- `server/adapters/gemini_adapter.py`
- `server/adapters/iflow_adapter.py`
- `server/services/skill_patcher.py`
- `server/services/agent_cli_manager.py`（如存在统一命令构造入口）
- `tests/unit/test_codex_adapter.py`
- `tests/unit/test_gemini_adapter.py`
- `tests/unit/test_iflow_adapter.py`
- `tests/unit/test_adapter_failfast.py`
