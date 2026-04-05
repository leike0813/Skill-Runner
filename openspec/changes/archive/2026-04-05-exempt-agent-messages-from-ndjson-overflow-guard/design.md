## Context

当前 shared NDJSON 运行时基础设施在两条路径上都执行相同的 `4096` 字节保护：

- `NdjsonLineBuffer`：live semantic parsing / raw line buffering
- `NdjsonIngressSanitizer`：audit/raw surfaces 的 sanitized truth

这保证了 live 与 audit 的一致性，但也意味着所有超长逻辑行都会被统一截断。对 `tool_result` 这类高体积 payload，这一策略能保护运行时内存和协议推进；但对 `agent.reasoning` 与 `agent.message`，它会直接截断正常对话正文，破坏可读性与 replay 事实。

## Goals / Non-Goals

**Goals:**

- 为 `agent.reasoning` 与 `agent.message` 增加共享、统一的 overflow guard 豁免。
- 保证豁免同时作用于 live semantic 和 audit/raw 路径。
- 保持非消息类 payload 的既有 overflow repair / sanitize / substitute 语义不变。
- 让 NDJSON-based engine parser 通过轻量预分类参与判定，而不是在某个 engine 内部做单点特判。

**Non-Goals:**

- 不改变 HTTP API、runtime event schema 或 FCMP/RASP 事件类型。
- 不为 `tool_result` / `command_execution` / `tool_call` 放宽截断策略。
- 不扩张到 `gemini`、`iflow` 这类不走 shared NDJSON live path 的引擎。
- 不引入双阈值或新的长度上限策略；本次对豁免消息完全不设 `4096` 截断。

## Decisions

### 1. 豁免判定下沉到 shared NDJSON 基础设施

在 `NdjsonLineBuffer` 与 `NdjsonIngressSanitizer` 上增加统一的 semantic exemption probe，输入为当前 logical line / stream，输出为：

- `reasoning`
- `assistant_message`
- `None`

理由：
- 截断发生在完整 parser 之前，不能只在某个 parser 的后处理阶段修补。
- live 与 audit 必须共享同一判定，否则会再次出现 live 保留全文、audit 仍被截断的事实漂移。

替代方案：
- 仅修改 engine parser 的后处理。否决，因为已经晚于 shared truncation。
- 只在 ingress 层豁免。否决，因为 live parser / raw publisher 仍会继续截断。

### 2. 由 NDJSON-based engine parser 提供轻量预分类

`codex`、`claude`、`opencode`、`qwen` 需要提供一个轻量“预分类”函数，供 shared buffer 在完整 parse 之前判断当前逻辑行是否属于：

- reasoning 文本
- assistant/agent message 文本

约束：
- 只有显式 reasoning/thinking 类 payload 进入 `reasoning`
- 普通 assistant 文本进入 `assistant_message`
- `tool_use` / `tool_result` / `command_execution` / `tool_call` 不豁免
- 未识别形态默认不豁免

理由：
- 各引擎 NDJSON 形态不同，但最终语义面已收敛。
- 预分类只需要“够判断豁免”，不需要完整重跑 parser。

### 3. 豁免只跳过 4KB guard，不跳过其他 sanitation

即使消息被豁免，也仍然要经过：

- JSON 合法性检查
- 既有 repair 流程
- 非法 JSON 的诊断逻辑

区别仅在于：不再因为超过 `4096` 字节而主动截断或替换该 logical line。

理由：
- 目标是保住长 agent 文本，不是绕过 NDJSON 健壮性约束。

### 4. 规范口径放在 `engine-adapter-runtime-contract`

本次只修改 `engine-adapter-runtime-contract` 的 delta spec，不扩张新的 capability。

理由：
- 行为变化是 shared adapter/runtime contract 的一部分。
- 不涉及新的外部接口或新的领域能力。

## Risks / Trade-offs

- [Risk] 长 reasoning / assistant message 不再受 4KB 限制，可能提高单行内存占用。 → Mitigation: 豁免范围严格限定为消息语义，不扩张到工具结果和命令输出。
- [Risk] 预分类规则与最终 parser 语义漂移。 → Mitigation: 用代表性 engine integration tests 锁住 reasoning / assistant / tool_result 的分类边界。
- [Risk] 只修 live 或只修 audit 导致事实不一致。 → Mitigation: 设计上要求 `NdjsonLineBuffer` 与 `NdjsonIngressSanitizer` 复用同一 probe 接口与判定逻辑。
