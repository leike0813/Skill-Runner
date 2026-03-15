## Context

运行链路会先生成引擎命令，再在 `_execute_process` 中执行平台归一化、依赖注入包装与子进程启动。  
本次问题的关键回归是：虽然已得到 `normalized_command`，但在 `runtime.dependencies` 注入成功分支又基于原始 `command` 重新包装，导致 Windows `.cmd` shim 重新进入最终执行链路。

Windows 参数截断根因在于 `.cmd` shim 通过 `cmd.exe` 转发参数（`%*`），会经历二次 tokenization。包含空格、引号、反斜杠或多行内容的 prompt 在该链路上存在被截断/改写风险。

同时，排障过程需要同时看到三层真相：

1. 原始命令（构建链路输入）
2. 实际执行命令（归一化 + 注入后的最终 argv）
3. 最终渲染 prompt（含输入路径渲染与 prompt override）

## Design Goals

1. 保证 Windows 下“归一化命令”在所有执行分支中都是唯一 base command。
2. 保证 `request_input.json` 记录的 effective argv 与真实执行完全一致。
3. 保证 prompt/argv 审计只在首 attempt 记录一次，避免多次重试污染排障基线。
4. 审计失败不得影响 run 主流程。
5. 显式规避 `.cmd -> cmd.exe -> %*` 参数转发路径，消除 Windows 侧参数截断风险。

## Design

### 1) 执行命令归一化优先

- `_execute_process` 在 `_create_subprocess` 前计算 `normalized_command`。
- Windows 命中 npm `.cmd` shim 时，重写为 `node <js_entry> <fixed_flags> <original_args>`。
- 所有后续分支（含 `runtime.dependencies` 的 `uv run` 包装）都必须以 `normalized_command` 为输入。
- 该重写的核心目标是绕过 `cmd.exe` 参数重解析，保持 Python `subprocess` argv 逐项传递语义，确保 prompt/path 等复杂参数不被截断。

### 2) 依赖注入分支一致性

- `probe_ok` 分支必须执行：
  - `command_to_execute = _wrap_command_with_uv(command=normalized_command, ...)`
- 禁止在该分支重新引用原始 `command`，避免归一化被覆盖。

### 3) 首 attempt 审计聚合

- 仅 `attempt=1` 写入 `.audit/request_input.json` 新增字段：
  - `rendered_prompt_first_attempt`
  - `spawn_command_original_first_attempt`
  - `spawn_command_effective_first_attempt`
  - `spawn_command_normalization_applied_first_attempt`
  - `spawn_command_normalization_reason_first_attempt`
- 写入时机位于 `command_to_execute` 最终确定后，确保与真实执行一致。

### 4) 审计写入回退策略

- `request_input.json` 不存在/损坏/写入失败时：
  - prompt 降级写 `.audit/prompt.1.txt`
  - argv 降级写 `.audit/argv.1.json`
- 降级仅用于审计可观测性，run 主流程继续执行。

## Non-Goals

- 不调整 engine-specific command builder 的业务参数语义。
- 不变更对外 HTTP API 或 runtime 协议字段。
- 不扩展到 `.ps1/.bat` 全量归一化规则（后续可独立变更）。
