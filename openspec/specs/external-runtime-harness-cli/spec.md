# external-runtime-harness-cli Specification

## Purpose
TBD - created by archiving change interactive-41-external-runtime-harness-conformance. Update Purpose after archive.
## Requirements
### Requirement: Harness CLI MUST 提供独立入口并保持与主服务解耦
系统 MUST 提供独立的 harness CLI 入口，运行于独立代码目录；其执行不依赖启动主服务 UI 或改写主服务路由行为。

#### Scenario: 独立入口可执行
- **WHEN** 用户在项目根目录调用 harness CLI
- **THEN** CLI 可以在不启动主服务开发服务器的前提下执行
- **AND** 主服务对外 API 路径与行为不因 harness 存在而改变

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

### Requirement: Harness CLI MUST 支持 translate 多级输出控制
系统 MUST 支持 `--translate 0|1|2|3`，并将其仅作为 harness 输出渲染控制参数；该参数 MUST NOT 透传至引擎进程。

#### Scenario: translate 参数不透传
- **WHEN** 用户执行 `start --translate 2 gemini ...`
- **THEN** harness 以 level=2 的格式渲染运行输出
- **AND** 实际引擎命令参数中不包含 `--translate`

### Requirement: Harness CLI MUST 在 translate=0 且终端可交互时实时透传
系统 MUST 在 `translate=0` 且当前 stdin/stdout/stderr 为 TTY 时采用实时终端透传模式，使交互体验与直接执行引擎命令一致。

#### Scenario: translate=0 使用实时透传
- **WHEN** 用户在真实终端中执行 `agent_harness codex`
- **THEN** harness 运行时实时显示引擎终端输出并允许即时键盘交互
- **AND** 运行结束后仍产出完整审计工件

### Requirement: Harness CLI MUST 标记运行时透传边界
系统 MUST 在引擎运行输出前后打印稳定分隔符，帮助用户区分“实时运行输出”与“harness 摘要输出”。

#### Scenario: 运行前后显示分隔符
- **WHEN** harness 启动一次引擎执行（start 或 resume）
- **THEN** 在运行开始前输出 `[agent:<engine>] ---------------- runtime begin ----------------`
- **AND** 在运行结束后输出 `[agent:<engine>] ---------------- runtime end ----------------`

#### Scenario: 分隔符不重复且包裹 translate 输出
- **WHEN** 用户使用任意 `--translate 0|1|2|3` 执行一次 run
- **THEN** `runtime begin` 与 `runtime end` 在该次 run 中各仅出现一次
- **AND** translate 结果输出位于 begin/end 分隔范围内
- **AND** CLI 不再额外输出第二套 translated begin/end 分隔符

### Requirement: Harness CLI MUST 在 runtime begin 前输出审计前置信息
系统 MUST 在 `runtime begin` 分隔符之前输出对齐 `agent-test-env` 的审计前置信息，至少包括 run_id、run_dir、executable、passthrough、translate_mode、injected_skills、config_roots。

#### Scenario: 审计前置信息位于 runtime begin 之前
- **WHEN** harness 启动一次引擎执行（start 或 resume）
- **THEN** stderr 在 `runtime begin` 前输出 `run_id/run_dir/executable/passthrough/translate_mode/injected_skills/config_roots`
- **AND** `runtime begin` 与 `runtime end` 分隔符仍各出现一次

### Requirement: Harness CLI MUST 提供简洁尾部摘要输出
系统 MUST 在运行结束后输出与 `agent-test-env` 对齐的简洁摘要，避免冗余审计字段占据控制台尾部。

#### Scenario: 尾部输出保持最小必要字段
- **WHEN** harness 完成一次 start 或 resume
- **THEN** 尾部摘要至少包含 `Run id`、`Run directory`、`Run handle`、`Session`、`<Start|Resume> complete. exitCode=...`
- **AND** 不在默认尾部摘要中打印 `status/completion/audit` 详细字段

### Requirement: Harness CLI MUST 支持基于句柄的 resume
系统 MUST 支持 `resume <handle> <message>`，并能根据句柄解析运行上下文后发起恢复执行。

#### Scenario: 句柄恢复执行
- **WHEN** 用户执行 `resume <handle8> "next step"`
- **THEN** harness 根据句柄找到对应运行上下文和 session handle
- **AND** 恢复调用使用 `<message>` 作为本轮输入继续执行

### Requirement: Harness CLI MUST 支持运行目录选择与复用
系统 MUST 支持 run selector（如 `--run-dir <selector>`）以复用已有 run 目录并新增 attempt。

#### Scenario: 复用 run 目录时新增 attempt
- **WHEN** 用户使用 `--run-dir` 指向一个已存在的 harness run
- **THEN** harness 在该 run 下追加新的 attempt 审计文件
- **AND** 不覆盖历史 attempt 工件

### Requirement: Harness CLI MUST 预留 opencode 引擎位并可能力降级
系统 MUST 接受 `opencode` 作为合法引擎标识，并提供与其他引擎同级的 start/resume 执行能力；当环境缺失 opencode CLI 时，MUST 返回安装或命令缺失错误而非静默降级。

#### Scenario: opencode start 走正式执行链路
- **WHEN** 用户执行 `agent_harness start opencode ...`
- **THEN** harness 通过 Adapter 生成并执行 opencode start 命令
- **AND** 不返回 `ENGINE_CAPABILITY_UNAVAILABLE`

#### Scenario: opencode resume 走正式执行链路
- **WHEN** 用户执行 `agent_harness resume <handle> <message>` 且对应 run 引擎为 opencode
- **THEN** harness 通过 Adapter resume 接口构建 `--session=<id>` 形态命令并继续执行

#### Scenario: opencode CLI 缺失时显式报错
- **WHEN** 用户执行 opencode start/resume 且运行环境缺失 opencode 可执行文件
- **THEN** harness 返回结构化缺失错误并附带可诊断信息
- **AND** MUST NOT 静默回退到其它引擎

