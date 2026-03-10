# FCMP / RASP Protocol Delta: Process Events v1

## 1. Scope

本工件定义本次后端协议增量（不含前端渲染改造）：

- 新增通用过程事件（RASP + FCMP）
- 增加 `message.promoted` 收敛标记
- 保留并兼容现有 `*.message.final`

## 2. Event Matrix

| RASP (internal) | FCMP (public) | Notes |
|---|---|---|
| `agent.reasoning` | `assistant.reasoning` | 中间推理过程 |
| `agent.tool_call` | `assistant.tool_call` | 工具调用过程 |
| `agent.command_execution` | `assistant.command_execution` | 命令执行过程 |
| `agent.message.promoted` | `assistant.message.promoted` | “将过程消息提升为 final”的显式标记 |
| `agent.message.final` | `assistant.message.final` | 最终消息（保留） |

命名边界：

- RASP 固定 `agent.*`
- FCMP 固定 `assistant.*`
- chat replay 角色保持 `assistant`

## 3. Common Payload Fields

过程事件及 promoted/final 扩展字段：

- `message_id: string`
- `summary: string`（过程/promoted 必填，final 可选）
- `classification: reasoning|tool_call|command_execution|promoted|final`（过程/promoted 必填，final 可选）
- `details: object`（过程/promoted 必填，final 可选）
- `text: string`（final 必填；过程/promoted 可选）

`raw_ref` 继续位于 envelope 层。

## 4. Sequence Semantics

1. 过程消息先即时发布为 `reasoning/tool/command`。
2. 收到回合结束信号后发布：
   - `*.message.promoted`
   - `*.message.final`
3. 若无回合结束信号：
   - 仅 `succeeded|waiting_user` 允许 fallback 提升
   - `failed|canceled` 禁止 fallback 提升

## 5. Example

```json
{
  "protocol_version": "fcmp/1.0",
  "run_id": "run-123",
  "seq": 42,
  "engine": "codex",
  "type": "assistant.message.promoted",
  "data": {
    "message_id": "msg-9",
    "summary": "准备向用户发出最终答复",
    "classification": "promoted",
    "details": { "from": "reasoning", "to": "final" },
    "text": "..."
  },
  "meta": { "attempt": 2 },
  "raw_ref": null
}
```

## 6. Frontend Guidance (for next change)

1. 先支持过程事件展示（reasoning/tool/command）。
2. 利用 `message_id` 关联 `promoted -> final`，实现平滑收敛展示。
3. 保持对无过程事件旧 run 的兼容（仅 `assistant.message.final` 仍可渲染）。
