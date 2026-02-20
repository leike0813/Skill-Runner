## Context

当前 `run_detail` 页面已经接入 management API 的状态、pending/reply、SSE 与 cancel 能力，但布局仍以“文件 + 日志面板”为中心，交互输入区域是独立的 pending 面板。实际 interactive 场景下，用户更需要持续查看 Agent 主输出并在同一视觉区域完成回复输入；同时长文件树和长文件预览会拉长页面，影响可用性与操作效率。

约束条件：
- 不新增后端协议，继续复用现有 `/v1/management/runs/*`。
- UI 仍为服务端模板 + 原生 JS + htmx 组合，不引入新前端框架。
- 页面需保持只读文件浏览、安全路径校验、SSE 断线重连与 cancel 语义。

## Goals / Non-Goals

**Goals:**
- 将 Run 详情页升级为“对话导向”布局：stdout 作为主对话窗口，输入框固定在主窗口下方。
- 将 stderr 拆分为独立窗口，避免与主对话内容混杂。
- 为文件树与文件预览增加最大高度和内部滚动，避免页面无限拉长。
- 保持现有 management API 契约不变，做到仅 UI 结构升级。

**Non-Goals:**
- 不改动后端交互协议（pending/reply/events/cancel 的请求与响应结构保持不变）。
- 不在本次实现中引入多轮消息持久化渲染（历史“气泡列表”语义）。
- 不改造 run 列表页与其他非 Run 详情页面的视觉体系。

## Decisions

### 1) 布局采用“三段式固定区块”
- 方案：页面分为文件区、对话区、错误区三个稳定区块。
  - 文件区：文件树与文件预览并排，二者都有固定 `max-height` 与 `overflow:auto`。
  - 对话区：stdout 主窗 + 底部回复输入。
  - 错误区：stderr 独立窗口。
- 选择原因：与当前功能契约最兼容，改造成本低，且能立即解决页面过长问题。
- 备选方案：
  - 单区 tabs（stdout/stderr/文件）：切换成本高，无法同时看到主对话与错误输出。
  - 全屏聊天页：重构范围过大，超出本 change 目标。

### 2) stdout 继续作为事件流主源，不引入新消息模型
- 方案：继续消费 `events` 的 `stdout/stderr/status/end`，stdout 文本增量渲染在主对话窗口。
- 选择原因：无需改动后端；兼容已有 offset 与重连逻辑。
- 备选方案：
  - 在前端解析结构化消息并渲染聊天气泡：当前后端未提供稳定消息结构，风险高。

### 3) 回复输入与 pending 状态合并为同一交互区域
- 方案：保留 pending/reply 语义，但将输入框固定在主对话区域底部；pending 存在时启用输入，无 pending 时展示提示态并禁用提交。
- 选择原因：减少视觉跳转，符合“对话式”操作流。
- 备选方案：
  - 继续独立 pending 卡片：可实现但割裂对话体验，与本次目标冲突。

### 4) stderr 独立展示并保持增量滚动
- 方案：stderr 单独卡片展示，独立滚动和自动滚动策略，不影响 stdout 主窗。
- 选择原因：提升异常排查效率，避免主对话被噪声淹没。
- 备选方案：
  - stderr 内联 stdout：信息混杂，阅读负担高。

## Risks / Trade-offs

- [风险] 固定高度可能在小屏幕上可视区域不足  
  → 缓解：使用响应式高度与媒体查询，在窄屏下降低各区块高度并保持滚动。

- [风险] 输入区固定后，waiting_user 与 running 状态切换时可能出现按钮可用性错乱  
  → 缓解：统一由 `pending` 结果驱动输入区 enable/disable，并在 `status/end` 事件后强制刷新一次 state。

- [风险] stdout 连续大流量输出导致前端节点过长  
  → 缓解：沿用现有增量机制并保留后续可选优化点（分段裁剪）为非本次范围。

## Migration Plan

1. 先改 `run_detail` 模板样式与 DOM 结构（不改接口调用路径）。
2. 调整前端脚本：将 pending/reply 控制与主对话输入区绑定。
3. 验证 SSE、pending/reply、cancel 在新布局下行为一致。
4. 更新 `docs/api_reference.md` 与 `docs/dev_guide.md` 的 Run 页面描述。
5. 运行 UI 相关单测与集成测试回归。

回滚策略：
- 若出现 UI 交互回归，可回滚 `server/assets/templates/ui/run_detail.html` 与相关文档，不影响后端 API。

## Open Questions

- 是否需要在本 change 内把 stdout 文本进一步结构化为“消息气泡”（当前建议不做，保持日志流语义）？
- 是否需要为 stderr 窗口增加“仅在有内容时高亮提示”交互（可作为后续增强）？
