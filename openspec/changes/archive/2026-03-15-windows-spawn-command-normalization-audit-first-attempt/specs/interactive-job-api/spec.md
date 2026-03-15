## ADDED Requirements

### Requirement: runtime.dependencies wrapping MUST preserve normalized spawn command
系统在执行 `runtime.dependencies` 注入包装时 MUST 以归一化后的命令作为 base command，不得回退到归一化前命令。

#### Scenario: Windows npm cmd shim remains normalized after dependency wrapping
- **GIVEN** Windows 平台上原始命令首参数为 npm `.cmd` shim
- **AND** 系统已得到归一化命令 `node <entry.js> ...`
- **WHEN** `runtime.dependencies` probe 成功并执行 `uv run` 包装
- **THEN** 最终执行 argv MUST 基于归一化命令拼接（`uv run ... -- node <entry.js> ...`）
- **AND** 最终执行 argv MUST NOT 回退为 `.cmd` shim 形式

#### Scenario: best-effort fallback still uses normalized base command
- **GIVEN** Windows 平台命令已完成归一化
- **WHEN** `runtime.dependencies` probe 失败并走 best-effort fallback
- **THEN** 系统 MUST 继续执行归一化命令
- **AND** MUST NOT 因 probe 失败恢复原始未归一化命令

### Requirement: Windows spawn argv MUST avoid cmd-shim truncation semantics
系统在 Windows 上执行 engine 命令时 MUST 避免经由 npm `.cmd` shim 的 `cmd.exe` 二次参数解析路径，以防复杂参数被截断或改写。

#### Scenario: quoted prompt and path args remain intact after normalization
- **GIVEN** Windows 平台下原始命令包含带空格、引号或反斜杠的 prompt/path 参数
- **WHEN** 系统执行命令归一化并启动子进程
- **THEN** 最终执行 argv MUST 通过 `node <entry.js> ...` 直启路径传递
- **AND** 参数项数量与顺序 MUST 与归一化输入一致
- **AND** 参数值 MUST NOT 被截断、拆分或重写
