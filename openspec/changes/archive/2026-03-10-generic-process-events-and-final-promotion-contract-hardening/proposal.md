## Why

当前协议里，RASP/FCMP 对“过程消息”和“最终消息”的表达过于扁平：

- RASP 主要是 `agent.message.final`，难以区分中间推理、工具调用、命令执行。
- FCMP 仅有 `assistant.message.final`，无法稳定承载“先过程、后收敛”为 final 的通用语义。
- 运行中与终态重放虽然已收敛到 live publisher 单源，但“message promoted -> final”的跨协议约束尚未固化。

这会导致两类问题：

1. 中间过程可观测性不足，后续前端增强缺少稳定协议输入。  
2. 引擎出现“同一回合多条 agent_message”时，缺少统一的 final 提升机制，容易把过程消息误当 final。

## What Changes

1. 升级 **RASP + FCMP** 的通用过程事件（非 engine-specific）：
   - RASP：`agent.reasoning` / `agent.tool_call` / `agent.command_execution` / `agent.message.promoted`
   - FCMP：`assistant.reasoning` / `assistant.tool_call` / `assistant.command_execution` / `assistant.message.promoted`
   - 保留现有 final：`agent.message.final` + `assistant.message.final`
2. 引入通用 `FinalPromotionCoordinator`：
   - 过程消息先发布为 reasoning/过程事件
   - 回合结束信号到达时发布 `*.message.promoted` + `*.message.final`
   - 无回合结束信号时，仅在 `succeeded` 或 `waiting_user` 兜底提升
   - `failed/canceled` 不兜底提升
3. 固化命名边界与映射不变量：
   - RASP 保持 `agent.*`
   - FCMP 与 chat 保持 `assistant.*`
   - 强制 `RASP agent.* -> FCMP assistant.* -> chat role=assistant`
4. 先做后端协议与合同收敛，不改前端消费逻辑；产出协议中间工件供后续前端 change 使用。

## Impact

- 无新增/删除 API 路由。
- `/protocol/history` 返回结构不变，但事件类型集合扩展。
- chat replay 继续使用 `role=assistant`，兼容现有消费端。
- 新增中间工件 `artifacts/fcmp_rasp_protocol_delta_process_events_v1.md` 作为下一次前端改造输入。
