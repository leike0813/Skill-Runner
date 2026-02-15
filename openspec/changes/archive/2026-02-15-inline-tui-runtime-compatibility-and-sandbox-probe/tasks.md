## 1. 启动策略调整

- [x] 1.1 将 sandbox 检查从阻断式（503）改为探测式（状态返回）
- [x] 1.2 保持 CLI 缺失/会话冲突等硬错误为失败路径
- [x] 1.3 在会话快照中补充 `sandbox_status` / `sandbox_message`

## 2. 可观测性修复

- [x] 2.1 WS 建连后立即推送 state 帧
- [x] 2.2 启动后追加握手输出，避免终端空白
- [x] 2.3 UI 展示 sandbox 状态（非阻断 warning）

## 3. 测试与回归

- [x] 3.1 更新服务层单测：unsupported/unknown sandbox 仍可启动
- [x] 3.2 更新路由层单测：不再因 sandbox 返回 503
- [x] 3.3 新增 WS 首帧行为测试（state first）
- [x] 3.4 执行 pytest + mypy

## 4. 文档更新

- [x] 4.1 更新 API/UI 文档：说明 sandbox 状态为观测信息、非默认阻断
- [x] 4.2 更新 README：说明三引擎均可启动 TUI，sandbox 状态以 UI 提示为准
