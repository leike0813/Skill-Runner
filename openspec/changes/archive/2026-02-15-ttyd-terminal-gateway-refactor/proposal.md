## Why

当前内嵌终端方案在真实部署中暴露出持续性问题：

1. 渲染与滚动行为不稳定（截断、滚动条异常、清屏异常）。
2. 选择/复制体验差，影响实际排障与鉴权操作。
3. 不同引擎 TUI 兼容性不一致，维护成本持续上升。

这些问题本质上来自“自维护 PTY + WebSocket + 前端终端渲染”的复杂链路。  
为了优先恢复稳定可用性，需要将终端承载能力收敛到成熟网关组件。

## What Changes

1. **终端网关重构**
   - 将现有内嵌终端会话实现重构为 `ttyd` 网关驱动。
   - UI 不再直接消费自建 PTY 流，而是消费 ttyd 提供的终端会话。

2. **采用 ttyd 方案**
   - 每次启动 TUI 时由后端受控拉起 ttyd 进程并绑定目标引擎命令。
   - 继续执行“单会话全局互斥”策略：同一时刻仅允许一个活跃 TUI 会话。

3. **兼容与安全保持**
   - 继续限制为固定引擎白名单命令（codex/gemini/iflow）。
   - 继续保留会话级隔离目录与受控环境变量注入。
   - 不开放任意 shell 命令输入入口。

## Impact

- `server/services/ui_shell_manager.py`（或等价服务）  
  - 从自建 PTY 管线切换到 ttyd 进程生命周期管理
- `server/routers/ui.py`  
  - 调整启动/停止/状态接口的会话元信息与错误语义
- `server/assets/templates/ui/engines.html`  
  - 终端展示容器改为 ttyd 嵌入视图（保留单会话操作）
- `tests/unit/test_ui_shell_manager.py`
- `tests/unit/test_ui_routes.py`
- 部署与依赖文档（README / containerization / API 文档）

