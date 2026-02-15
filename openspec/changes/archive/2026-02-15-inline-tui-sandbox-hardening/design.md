## Context

内嵌 TUI 当前通过 `ttyd` 启动三引擎 CLI，重点用于认证状态与运行健康检查。  
该路径应采用“最小权限 + 强隔离”原则，而不是沿用 RUN 自动执行路径的权限模型。

## Goals

1. Gemini 内嵌 TUI 启动时在可用环境显式启用 sandbox。
2. iFlow 内嵌 TUI 固定非沙箱启动，并返回显式告警。
3. 三引擎在内嵌 TUI 路径统一禁用 shell 工具能力。
4. 明确并固化 TUI 路径与 RUN 路径的配置隔离。
5. 暂不启用 fail-closed，继续保留 sandbox 状态可观测。

## Non-Goals

1. 不修改 RUN 自动执行路径的权限与策略。
2. 不在本 change 中引入“探测失败即阻断启动”。
3. 不引入多会话并发能力。

## Design

### 1) TUI 启动参数矩阵

- `codex`:
  - 保持受控沙箱参数；
  - 通过 CLI 覆盖项显式关闭 shell 相关工具能力（例如 `features.shell_tool=false`、`features.unified_exec=false`）。
- `gemini`:
  - 在容器沙箱运行时可用时，TUI 启动命令追加 `--sandbox`。
- `iflow`:
  - TUI 启动命令不追加 `--sandbox`。
  - `sandbox_status/sandbox_message` 明确标注“当前非沙箱 + 原因（iFlow 沙箱依赖 Docker 镜像执行）”。

### 2) 会话级安全配置（TUI 专用）

对每个 `session_dir` 写入会话级配置（项目局部配置）：

- `.gemini/settings.json`
  - `tools.sandbox` 按运行时探测结果设置（可用时为 `true`）
  - 禁用 shell 工具（`run_shell_command`）
  - 关闭自动放行（`tools.autoAccept=false`）
- `.iflow/settings.json`
  - `sandbox=false`
  - 禁用 shell 工具（`ShellTool` / `run_shell_command`）
  - 关闭自动放行（`autoAccept=false`，非 yolo 审批模式）

该配置仅作用于 TUI 会话目录，不进入 RUN adapter 的配置融合流程。

### 3) 路径隔离约束

在 `ui_shell_manager` 内固化边界：

1. TUI 会话构建使用单独的安全配置构建函数；
2. 禁止读取 RUN path enforced config 作为 TUI 会话策略来源；
3. 测试中加入“配置来源隔离”断言，防止回归耦合。

### 4) 启动策略

保留当前非阻断策略：

- 即使 sandbox 探测状态为 `unknown/unsupported`，启动接口仍可返回成功；
- Gemini 仍尝试“启动参数 + 会话配置”的 sandbox 与禁 shell 策略；
- iFlow 固定为非沙箱并保留显式告警，同时确保禁 shell 策略生效。

## Risks & Mitigations

1. **风险：不同 CLI 版本的工具名/配置键不一致**
   - 缓解：在实现中使用“参数 + 会话配置”双保险，并补充版本兼容测试。
2. **风险：禁用 shell 导致某些 UI 检查动作不可用**
   - 缓解：明确内嵌 TUI 用途为健康检查，不承诺交互式命令执行能力。
3. **风险：后续开发误复用 RUN 配置**
   - 缓解：在 spec 与测试中固化“TUI/RUN 隔离”要求。
