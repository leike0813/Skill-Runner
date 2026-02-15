## 1. 启动参数强化（TUI）

- [x] 1.1 在 `ui_shell_manager` 为 Gemini TUI 启动参数追加 `--sandbox`
- [x] 1.2 在 `ui_shell_manager` 将 iFlow TUI 固定为非沙箱启动，并返回显式告警信息
- [x] 1.3 为 Codex TUI 启动显式添加禁用 shell/unified_exec 的 CLI 覆盖项

## 2. 会话级安全配置（TUI 专用）

- [x] 2.1 在 `session_dir` 生成 `.gemini/settings.json`，禁用 shell 工具并关闭自动放行
- [x] 2.2 在 `session_dir` 生成 `.iflow/settings.json`，禁用 shell 工具并关闭自动放行
- [x] 2.3 确保该配置仅作用于内嵌 TUI 会话，不进入 RUN 路径

## 3. 测试

- [x] 3.1 单测：Gemini 启动命令在可用时包含 `--sandbox`
- [x] 3.2 单测：iFlow 启动命令不包含 `--sandbox` 且返回非沙箱告警
- [x] 3.3 单测：Codex 启动命令包含禁用 shell 工具的覆盖项
- [x] 3.4 单测：会话目录配置包含禁 shell 与非 yolo 设定
- [ ] 3.5 单测：TUI 路径不会读取 RUN enforced config

## 4. 文档

- [x] 4.1 更新 API/README：说明内嵌 TUI 为最小权限路径，默认禁 shell
- [x] 4.2 文档中明确 TUI 路径与 RUN 路径权限模型分离
- [x] 4.3 保留“当前非 fail-closed，仅观测 sandbox 状态”的阶段性说明
