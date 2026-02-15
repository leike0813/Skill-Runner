## MODIFIED Requirements

### Requirement: 系统 MUST 提供受控的 UI 鉴权终端会话
系统 MUST 在 `/ui/engines` 页面内提供终端会话能力，并在 managed 环境中执行预置引擎命令。

#### Scenario: Gemini 启动时显式启用 sandbox
- **WHEN** 用户在 `/ui/engines` 启动 `gemini` TUI
- **THEN** 系统在容器沙箱运行时可用时追加 `--sandbox`
- **AND** 会话状态仍返回 sandbox 探测结果用于可观测

#### Scenario: iFlow 启动时固定非沙箱并给出告警
- **WHEN** 用户在 `/ui/engines` 启动 `iflow` TUI
- **THEN** 系统启动命令不包含 `--sandbox`
- **AND** 会话状态返回 `sandbox_status=unsupported`
- **AND** `sandbox_message` 明确说明 iFlow 沙箱依赖 Docker 镜像执行，与当前内嵌 TUI 设计不一致

### Requirement: 系统 MUST 将内嵌 TUI 作为最小权限路径
系统 MUST 在内嵌 TUI 路径禁用三引擎 shell 工具能力，避免通过 shell 工具绕过写入边界。

#### Scenario: Codex TUI 禁用 shell 工具
- **WHEN** 用户启动 Codex TUI
- **THEN** 会话配置/启动参数显式禁用 shell 与 unified_exec 能力
- **AND** 不允许通过该工具链在会话内执行 shell 命令

#### Scenario: Gemini TUI 禁用 run_shell_command
- **WHEN** 用户启动 Gemini TUI
- **THEN** 会话级 `.gemini/settings.json` 禁用 `run_shell_command` 相关工具能力
- **AND** 自动放行策略保持关闭

#### Scenario: iFlow TUI 禁用 ShellTool
- **WHEN** 用户启动 iFlow TUI
- **THEN** 会话级 `.iflow/settings.json` 禁用 `ShellTool`（及兼容 shell 工具名）
- **AND** 审批模式不得为 yolo
- **AND** `sandbox` 设置保持为 `false`

### Requirement: 系统 MUST 保持 TUI 与 RUN 路径策略隔离
系统 MUST 将内嵌 TUI 路径视为独立安全域，不得复用 RUN 路径的高权限配置融合逻辑。

#### Scenario: TUI 会话使用独立安全配置
- **WHEN** 系统创建 `data/ui_shell_sessions/<session_id>` 会话目录
- **THEN** TUI 会话安全策略仅由该会话目录内配置与 TUI 启动参数决定
- **AND** 不读取 RUN adapter 的 enforced 配置作为会话权限来源

### Requirement: 系统 MUST 暂保持 sandbox 非阻断启动
在本阶段，系统 MUST 不因 sandbox 探测结果为 `unsupported/unknown` 直接拒绝启动，但必须保留状态可观测。

#### Scenario: sandbox 状态未知但允许启动
- **WHEN** 用户启动任一引擎 TUI 且探测结果为 `unsupported` 或 `unknown`
- **THEN** 系统仍可启动会话
- **AND** UI 明确展示对应状态
- **AND** 系统仍应应用该引擎的禁 shell 策略
