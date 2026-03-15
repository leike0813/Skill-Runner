## Why

Windows 本地运行在 agent CLI 子进程拉起环节存在两类可追溯性与一致性风险：

1. npm `.cmd` shim 在 Windows 下会经过 `cmd.exe` 参数重解析，可能触发引号/反斜杠语义漂移与参数截断；若 `runtime.dependencies` 注入后错误地回包原始命令，会导致该风险重新进入执行链路。
2. 审计链路缺少“首 attempt 实际执行命令 + 首次渲染 prompt”的统一落盘，难以定位“同目录手工复现可成功、平台内调度失败”的差异。

需要将“执行命令真相”与“prompt 真相”固化到同一审计入口，保证后续可复盘、可比对、可归因。

## What Changes

- 在通用执行链路中明确 Windows `.cmd` shim 归一化优先级：将 `.cmd` 启动改写为 `node + js entry` 直启，绕过 `cmd.exe` 二次参数解析，避免参数截断。
- 依赖注入（`runtime.dependencies`）成功时，`uv run` 包装必须继续使用归一化后的 base command，禁止回退原始 `.cmd`。
- 审计收敛到 `.audit/request_input.json`（仅首 attempt）：
  - `rendered_prompt_first_attempt`
  - `spawn_command_original_first_attempt`
  - `spawn_command_effective_first_attempt`
  - `spawn_command_normalization_applied_first_attempt`
  - `spawn_command_normalization_reason_first_attempt`
- 审计写入失败时允许降级写回退文件（`prompt.1.txt` / `argv.1.json`），且不阻断主执行流程。

## Capabilities

### Modified Capabilities

- `interactive-job-api`
- `run-audit-contract`

## Impact

- Affected code:
  - `server/runtime/adapter/base_execution_adapter.py`
  - `server/runtime/adapter/common/prompt_builder_common.py`
  - `tests/unit/test_adapter_failfast.py`
  - 与 adapter 命令构建/执行相关的引擎适配单测
  - `docs/run_artifacts.md`
- API impact: None.
- Protocol impact: None.
