## Design Overview

本 change 采用“两层结构”：

1. **Shared Core（纯状态机）**
   - 输入：chat replay 事件（按 seq）
   - 输出：可渲染模型（普通消息条目 + 思考气泡条目）
   - 责任：
     - 连续 `assistant_process` 聚合到同一思考气泡
     - 默认折叠，折叠态只展示最后一条
     - 遇到边界事件（`assistant_final` / `user` / `system`）后关闭当前思考气泡，后续过程事件新开气泡
     - `assistant_final` 到达时执行去重（先 message_id，后同 attempt 规范化文本精确匹配）

2. **Renderer Adapter（双端独立）**
   - E2E adapter：沿用前端现有 chat-bubble 风格，轻量展示过程条目
   - 管理 UI adapter：沿用管理端 chat-item 风格，展示更多元信息（process_type/seq/attempt）
   - 两端共享同一状态机，不共享 DOM/CSS 实现。

## Backend Derivation

在 chat replay derivation 中新增映射：

- `assistant.reasoning` -> `role=assistant, kind=assistant_process, correlation.process_type=reasoning`
- `assistant.tool_call` -> `role=assistant, kind=assistant_process, correlation.process_type=tool_call`
- `assistant.command_execution` -> `role=assistant, kind=assistant_process, correlation.process_type=command_execution`

并携带：
- `correlation.message_id`（可选）
- `correlation.fcmp_seq`
- `correlation.summary/details/classification`（可选）

`assistant.message.promoted` 不生成 chat replay 条目。

## Dedupe Rule

当收到 `assistant_final`：

1. 先在同 attempt 的思考条目中按 `message_id` 精确匹配删除。
2. 若 final 无 `message_id`，按规范化文本（压缩空白 + trim）精确匹配删除。
3. 删除后若思考气泡为空，则回收该气泡，不渲染空块。

## Compatibility

- 旧 run 不包含 `assistant_process` 时，渲染回退为现有行为（仅普通消息气泡）。
- chat/history 路由与响应外壳不变，新增 kind 属于向后兼容扩展。
