## Why

当前内嵌终端存在两个阻塞问题：

1. Codex TUI 点击启动后，前端看起来“无输出”，用户无法判断是否真的进入了交互状态。
2. Gemini / iFlow 在现有 fail-closed 规则下直接返回 `503 sandbox_unavailable`，导致实际不可用。

这使得内嵌终端在“本地部署 + 多引擎调试/鉴权”场景下可用性不足。当前阶段应先恢复可用性，再补齐沙箱能力探测与可观测。

## What Changes

1. **调整启动策略（临时去掉 fail-closed）**
   - TUI 启动不再因为 sandbox 探测失败直接拒绝（不再默认 503）。
   - 对 codex/gemini/iflow 采用“先启动，后标注沙箱状态”的策略。

2. **引入沙箱探测结果可观测**
   - 启动前/启动后执行 lightweight probe（不触发 token 消耗）。
   - 将 `supported / unsupported / unknown` 状态返回给 UI 并写入日志。

3. **修复“启动成功但无输出”的体验问题**
   - WebSocket 连接建立后立即推送一次会话状态帧。
   - 启动后写入最小握手提示（例如 session/engine/pid），确保终端有即时可见反馈。

4. **保持安全边界不退化**
   - 继续保留白名单命令、单会话互斥、会话隔离目录、受控 env 注入。
   - 本次仅放宽“沙箱不可用即拒绝启动”这一条，不放开任意命令执行。

## Impact

- `server/services/ui_shell_manager.py`
- `server/routers/ui.py`
- `server/assets/templates/ui/engines.html`
- `tests/unit/test_ui_shell_manager.py`
- `tests/unit/test_ui_routes.py`
- `docs/api_reference.md`
- `README.md`, `README_CN.md`

