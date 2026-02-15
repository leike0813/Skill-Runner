## Why

当前 UI 内嵌终端存在三个核心问题：

1. 命令模型不匹配实际 CLI 能力。现有 `login/auth/version/interactive` 多模式中，`gemini` 与 `iflow` 的登录子命令并不稳定或不存在，导致启动失败。
2. 渲染链路不适配 TUI。当前以 `<pre>` + 轮询文本的方式展示输出，无法正确处理 ANSI/VT 控制序列与光标重绘，Gemini/iFlow 等复杂 TUI 出现乱码与错位。
3. 交互路径冗余。独立页面 `/ui/engines/auth-shell` 与引擎管理页面割裂，不符合“在引擎页直接进入 TUI”的使用目标。

为保证本地/容器部署中的鉴权与观测体验一致，需要将该能力重构为“引擎页内嵌 TUI 终端”模型。
同时，需要补上“交互式 TUI 可能越权操作宿主文件系统”的风险防护。

## What Changes

1. **终端入口重构（页面内嵌）**
   - 在 `/ui/engines` 页面下方直接集成终端区域。
   - 每个引擎仅提供一个动作：`在内嵌终端中启动 TUI`。
   - 移除独立页面 `/ui/engines/auth-shell`（直接下线）。

2. **命令模型简化**
   - 每个引擎只保留一个白名单命令：
     - `codex`
     - `gemini`
     - `iflow`
   - 不再暴露 `login/auth/version/interactive` 模式切换。

3. **渲染与传输升级**
   - 前端引入 `xterm.js` 终端仿真（本地静态资源），替换 `<pre>` 文本渲染。
   - 后端提供 WebSocket 双向通道（TTY 输出流 + 键盘输入），确保复杂 TUI 可用。
   - 保持 UTF-8 文本路径，避免乱码与控制序列原样泄露。
   - 不依赖浏览器访问外部 CDN，支持离线/内网部署。

4. **会话控制保持强约束**
   - 继续维持“全局同一时间仅一个活跃会话”。
   - 保留 `Stop` 终止能力（包含子进程清理）。

5. **防逃逸与沙箱硬化（fail-closed）**
   - 每次会话使用独立目录：`data/ui_shell_sessions/<session_id>`。
   - 可写范围严格限制为：`session_dir` + `agent_home`（鉴权文件所需）。
   - 启动前执行 sandbox 能力探测/校验；若无法确认生效则拒绝启动（fail-closed），不允许降级裸跑。
   - 优先使用 CLI 启动参数注入沙箱；若某引擎不支持启动参数，则使用该引擎配置注入并做生效校验。

6. **按钮交互策略（按你的选择 B）**
   - 不预先禁用按钮。
   - 允许用户点击启动，若 sandbox 不可用则立即返回明确错误并在终端区域展示。

## Impact

- 受影响模块：
  - `server/services/ui_shell_manager.py`
  - `server/routers/ui.py`
  - `server/main.py`（静态资源挂载）
  - `server/assets/templates/ui/engines.html`
  - `server/assets/static/*`（xterm.js / xterm.css）
  - `Dockerfile`（静态资源入镜像）
  - `tests/unit/test_ui_routes.py`
  - `tests/unit/test_ui_shell_manager.py`
  - `README.md` / `README_CN.md` / `docs/api_reference.md`
- 安全边界：
  - 仍为白名单命令，不开放任意 shell。
  - 仍受 UI Basic Auth 保护。
  - sandbox 不可用时拒绝启动，不降级执行。
