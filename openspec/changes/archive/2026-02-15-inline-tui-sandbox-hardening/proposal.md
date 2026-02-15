## Why

当前内嵌 TUI 路径仍存在高风险权限问题：

1. iFlow 的沙箱机制依赖 Docker 镜像执行，直接在内嵌 TUI 路径启用沙箱参数会导致启动不稳定或失败。
2. 三引擎在内嵌 TUI 中均可通过 shell 工具触发工作区外写入，用户批准后存在逃逸风险。
3. 内嵌 TUI 的安全边界应与 RUN 自动执行路径解耦，但目前缺少明确约束，容易误复用 RUN 配置。

内嵌 TUI 的定位是“受控健康检查入口”，不是任务执行入口，因此需要最小权限与显式隔离。

## What Changes

1. **明确内嵌 TUI 启动参数中的沙箱策略**
   - Gemini 启动 TUI 在容器沙箱运行时可用时追加 `--sandbox`。
   - iFlow 启动 TUI 不使用沙箱模式，并在会话状态中显式返回告警说明。
   - Codex 启动 TUI 维持受控沙箱模式，并显式关闭可执行 shell 的工具链路。

2. **在内嵌 TUI 路径禁用三引擎 shell 工具能力**
   - Codex：禁用 `shell`/`unified_exec` 相关工具能力。
   - Gemini：禁用 `run_shell_command` 相关工具能力。
   - iFlow：禁用 `ShellTool`/`run_shell_command` 相关工具能力。

3. **明确内嵌 TUI 与 RUN 路径配置隔离**
   - 内嵌 TUI 仅使用会话级（session_dir）安全配置与启动参数。
   - 不复用 RUN 路径的 adapter/enforced 配置合并逻辑。

4. **阶段性保持非 fail-closed 策略**
   - 当前 change 不将“沙箱探测失败”作为启动阻断条件。
   - 系统仍需返回并展示 sandbox 状态，供后续切换为 fail-closed 做验证依据。

## Impact

- `server/services/ui_shell_manager.py`
- `tests/unit/test_ui_shell_manager.py`
- `tests/unit/test_ui_routes.py`（如需补充路由侧约束断言）
- `docs/api_reference.md`
- `README.md`
- `README_CN.md`
