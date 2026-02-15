## Context

上一轮变更已引入受控终端会话管理，但当前实现是“独立页面 + 文本轮询渲染”，更像日志观察器，而非可交互 TUI 终端。

本次重构目标是让用户在 `/ui/engines` 页面就地启动并操作 Agent CLI 的原生 TUI，并保持单会话与白名单安全边界不变。

## Goals

1. 每个引擎仅保留一个动作：打开对应 CLI 的 TUI。
2. 终端渲染可正确处理 ANSI/VT 序列、光标移动、清屏与重绘。
3. 引擎页面内嵌终端，不再依赖独立 auth-shell 页面。
4. 单会话互斥、停止终端、超时清理策略继续有效。
5. 启动路径具备防逃逸约束：sandbox 不可确认生效则拒绝启动（fail-closed）。
6. 终端前端资源不依赖外部 CDN，支持内网/离线部署。

## Non-Goals

- 不支持多会话并发。
- 不开放任意命令执行。
- 不在本次引入会话录屏或历史持久化。

## Architecture

### 1) 命令层

`UiShellManager` 的白名单从多模式缩减为每引擎一个命令：

- `codex-tui` -> `codex`
- `gemini-tui` -> `gemini`
- `iflow-tui` -> `iflow`

接口层仅接收 `engine` 或命令 ID，不接收原始 shell 文本。

### 1.1) 会话工作目录与写入边界

- 每次会话创建隔离目录：`data/ui_shell_sessions/<session_id>`。
- TUI 进程 `cwd` 固定为该 `session_dir`。
- 设计上的可写白名单仅包含：
  - `session_dir`
  - `agent_home`（保存鉴权凭证）
- 其他路径默认不可写；若某引擎无法实现该约束，则该引擎本次会话拒绝启动。

### 1.2) Sandbox 约束策略

- 启动前执行两段校验：
  1. **配置就绪校验**：确认当前引擎 sandbox 配置/参数可注入。
  2. **可用性校验**：确认运行环境满足该引擎 sandbox 运行条件。
- 启动时优先采用 CLI 参数注入 sandbox；若该引擎参数不可用，则退回到受控配置文件注入。
- 任一校验失败时返回结构化错误（`sandbox_unavailable`），不启动进程（fail-closed）。

### 2) 传输层

- 新增 WebSocket 会话通道（建议路径：`/ui/engines/tui/ws`）。
- 前端通过 WebSocket 接收 PTY 输出字节流，并发送按键输入。
- 后端仍维护 ring buffer（用于重连恢复/短时回放），但主通道改为流式。

### 3) 展示层

- `/ui/engines` 页面新增内嵌终端卡片（xterm.js）。
- 在引擎列表中每行提供“在内嵌终端中启动 TUI”按钮。
- 终端区域提供：
  - 当前会话状态（running/terminated/error/timeout）
  - Stop 按钮
  - 错误提示区域
- 按钮策略采用 **B**：按钮始终可点击；点击后若 sandbox 不可用，立即显示错误反馈（不预禁用）。
- xterm 资源通过本地静态路径加载（如 `/ui-static/xterm/*`），不使用 CDN。

### 4) 路由收敛

- 下线 `/ui/engines/auth-shell` 页面路由（返回 404）。
- 终端相关操作收敛到 `/ui/engines` 页面所需接口与 WS 通道。
- 在应用层挂载静态资源目录供 UI 加载终端脚本与样式。

## Security

1. 命令白名单固定，且不接受参数注入。
2. 继续复用 UI Basic Auth（HTTP + WebSocket）。
3. 会话生命周期受超时与显式停止控制。
4. 会话目录隔离，写入边界仅 `session_dir` + `agent_home`。
5. sandbox 校验失败时 fail-closed，禁止降级裸跑。

## Failure Handling

1. 启动失败：返回结构化错误（CLI 不存在/依赖缺失）。
2. sandbox 不可用：返回 `sandbox_unavailable`，并附可操作说明。
3. WS 断开：会话仍可存活，允许前端重连并继续附着。
4. Stop 执行失败：记录错误并回传失败原因。

## Testing Strategy

1. 服务层：
   - 命令映射仅三项；
   - 单会话互斥；
   - Stop 与超时路径。
   - sandbox 校验失败走 fail-closed。
   - 会话目录隔离与写边界生效。
2. 路由层：
   - `/ui/engines/auth-shell` 为 404；
   - WS 鉴权校验；
   - 启动/停止接口状态码。
3. UI 层：
   - 引擎页内出现终端区域与启动按钮；
   - xterm.js 初始化脚本存在且来自本地静态路径；
   - 启停按钮状态切换逻辑；
   - sandbox 失败时按钮点击后的即时错误展示。
