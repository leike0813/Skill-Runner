## Why

当前系统只把 agent 输出中的最终 JSON 作为成功主路径。只要 stdout/stream 中的 JSON 无法解析，或者解析后不满足 `output.schema`，run 即使已经在工作目录里产出了正确的最终结果 JSON，也会被判定为失败。

这会带来一个高频误伤场景：skill 实质业务执行成功，但最后一步的 agent 结构化输出不合规，导致整个 run 失败。对于已经用脚本稳定落盘结果文件的 skill，这种失败是可恢复的。

## What Changes

- 在终态标准化阶段增加结果文件兜底恢复：
  - 当 `exit_code == 0` 且主路径没有得到合法最终 JSON 时，递归扫描 `run_dir` 内的结果文件。
- 结果文件名默认采用 `<skill-id>.result.json`，并允许通过 `runner.json.entrypoint.result_json_filename` 覆盖。
- 命中文件后，若其 JSON 合法且通过 output schema，则直接作为最终 `output_data`。
- 补齐 runner manifest 合同、package validator 和 orchestrator 回归测试。

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `output-json-repair`: 在 deterministic JSON 解析修复失败后，系统可进入结果文件兜底恢复。
- `run-file-contract`: run 工作目录内的结果文件可作为终态输出恢复来源。
- `skill-package-validation-schema`: `runner.json` 合同支持声明 `entrypoint.result_json_filename`。

## Impact

- Affected code:
  - `server/services/orchestration/run_result_file_fallback.py`
  - `server/services/orchestration/run_job_lifecycle_service.py`
  - `server/contracts/schemas/skill/skill_runner_manifest.schema.json`
- Affected tests:
  - `tests/unit/test_job_orchestrator.py`
  - `tests/unit/test_skill_package_validator.py`
- No public HTTP API changes; observable change is that some previously failed runs now succeed when a valid result file exists in the run workspace.
