## Why

当前对话区只稳定消费 `assistant_final`，无法表达 FCMP 新增的过程事件（`assistant.reasoning` / `assistant.tool_call` / `assistant.command_execution`）。

结果是：
- 用户看不到 agent 的中间思考过程。
- 过程内容与 final 内容可能重复渲染，影响可读性。
- E2E 与管理 UI 在后续扩展时容易形成两套漂移实现。

## What Changes

1. 将 FCMP 过程事件映射为 chat replay 可消费的通用 kind（`assistant_process`）。
2. 前端引入“共享状态机 + 双端独立渲染适配器”：
   - 状态机统一处理过程分组、折叠/展开、边界切换、final 去重。
   - E2E 与管理 UI 维持各自样式与内容粒度。
3. `assistant.message.promoted` 仅作为边界语义，不直接渲染为正文气泡。
4. 更新 API reference 与相关 specs，明确 chat/history 事件语义扩展（无新路由）。

## Impact

- 无新增/删除 HTTP API。
- chat replay 事件 kind 增量扩展：新增 `assistant_process`。
- 前端对话区渲染行为增强，但不影响 run 状态机、FCMP/RASP 主协议语义。
