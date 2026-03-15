## 1. OpenSpec Artifacts

- [x] 1.1 新增 change `windows-spawn-command-normalization-audit-first-attempt`。
- [x] 1.2 补充 proposal/design/tasks 与 capability spec delta。

## 2. Command Execution Consistency

- [x] 2.1 在通用执行链路引入 Windows npm `.cmd` shim 归一化（`node + js entry`）。
- [x] 2.2 修复 `runtime.dependencies` 注入成功分支：`uv` 包装必须基于归一化命令。
- [x] 2.3 保证最终 `spawn_command_effective_first_attempt` 与真实执行 argv 一致。

## 3. First-Attempt Audit Enrichment

- [x] 3.1 仅首 attempt 写入 `rendered_prompt_first_attempt`。
- [x] 3.2 仅首 attempt 写入 `spawn_command_*_first_attempt` 四个字段。
- [x] 3.3 `request_input.json` 写入失败时降级写 `.audit/prompt.1.txt` 与 `.audit/argv.1.json`。

## 4. Validation

- [x] 4.1 增加/更新回归单测覆盖 `uv` 分支不回退原始 `.cmd`。
- [x] 4.2 覆盖 attempt=1 写入与 attempt>1 不覆盖行为。
- [x] 4.3 覆盖 `request_input.json` 损坏时的回退写入行为。
- [x] 4.4 增加 Windows 参数完整性回归：带空格/引号/反斜杠的 prompt 与路径参数在归一化后不得截断、不得重排。
