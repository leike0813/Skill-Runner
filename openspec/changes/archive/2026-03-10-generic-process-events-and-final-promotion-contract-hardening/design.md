## Design Overview

本 change 采用“通用过程事件 + 统一提升协调器”的方式，避免把 Codex 特性耦合进核心合同。

### 1. 事件层模型

#### RASP（内部审计语义）
- `agent.reasoning`
- `agent.tool_call`
- `agent.command_execution`
- `agent.message.promoted`
- `agent.message.final`（保留）

#### FCMP（对外对话语义）
- `assistant.reasoning`
- `assistant.tool_call`
- `assistant.command_execution`
- `assistant.message.promoted`
- `assistant.message.final`（保留）

### 2. 通用字段

新增过程事件与 promoted/final 扩展字段使用统一 payload 形状：

- `message_id`：同一条消息语义 ID
- `summary`：短摘要（用于列表渲染）
- `details`：结构化补充信息（对象）
- `classification`：`reasoning|tool_call|command_execution|promoted|final`
- `text`：可选全文（final 必填）

`raw_ref` 继续使用事件 envelope 级字段，不改位置。

### 3. FinalPromotionCoordinator

协调器职责：

1. 接收“可提升消息”（通常来自 parser 的 `assistant_message`）。
2. 先发布 reasoning 事件。
3. 当收到“回合结束信号”（例如 turn completed）时，提升最新候选：
   - 发布 `*.message.promoted`
   - 随后发布 `*.message.final`
4. 若未收到回合结束信号：
   - 仅在状态收敛到 `succeeded|waiting_user` 时允许兜底提升
   - `failed|canceled` 禁止兜底提升

### 4. 引擎接入边界

本次先接 Codex，但保持通用协议内核：

- 引擎特有提取规则放在 adapter profile 声明。
- parser 输出统一过程事件输入；核心层不写 Codex 样式硬编码。
- 其他引擎后续只需补 parser/profile，不改协议核心。

### 5. 一致性与不变量

新增并强化以下不变量：

- RASP `agent.*` 与 FCMP `assistant.*` 命名边界不可混用。
- `message.promoted` 必须先于同 `message_id` 的 `message.final`。
- `failed/canceled` 场景不得触发兜底提升。
- chat replay 的 assistant 角色仅由 FCMP `assistant.*` 推导，不直接消费 RASP 命名。
