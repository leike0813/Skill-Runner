## MODIFIED Requirements

### Requirement: Harness CLI MUST 支持 start 与 passthrough 参数透传
系统 MUST 支持 `start [--auto] <engine> [passthrough-args...]`。  
当未指定 `--auto` 时，Harness MUST 使用 `execution_mode=interactive`；指定 `--auto` 时 MUST 使用 `execution_mode=auto`。  
除 harness 自身控制参数外，剩余参数 MUST 按顺序透传至目标引擎命令。

#### Scenario: start 默认 interactive
- **WHEN** 用户执行 `agent_harness start codex --json --full-auto -p skill-runner-harness "hello"`
- **THEN** harness 以 `execution_mode=interactive` 启动本次 attempt
- **AND** `--json --full-auto -p skill-runner-harness "hello"` 原样透传给 codex 命令

#### Scenario: start 使用 --auto 显式切换
- **WHEN** 用户执行 `agent_harness start --auto codex --json --full-auto -p skill-runner-harness "hello"`
- **THEN** harness 以 `execution_mode=auto` 启动本次 attempt
- **AND** `--auto` 不出现在最终引擎命令参数中

### Requirement: Harness CLI MUST 支持“直接引擎语法”并与原生命令等价
系统 MUST 支持 `[--auto] <engine> [passthrough-args...]` 直接调用语法，并在 managed 运行环境中保持与直接执行引擎命令一致的参数语义。  
当未指定 `--auto` 时，Harness MUST 默认 `execution_mode=interactive`；指定 `--auto` 时 MUST 使用 `execution_mode=auto`。

#### Scenario: 直接语法默认 interactive
- **WHEN** 用户执行 `agent_harness codex exec --json --skip-git-repo-check --full-auto "Hello."`
- **THEN** harness 在 managed 环境中执行等价于 `codex exec --json --skip-git-repo-check --full-auto "Hello."` 的命令
- **AND** 本次 attempt 的 execution mode 为 `interactive`

#### Scenario: 直接语法使用 --auto
- **WHEN** 用户执行 `agent_harness --auto codex exec --json --skip-git-repo-check --full-auto "Hello."`
- **THEN** harness 在 managed 环境中执行等价于 `codex exec --json --skip-git-repo-check --full-auto "Hello."` 的命令
- **AND** 本次 attempt 的 execution mode 为 `auto`
