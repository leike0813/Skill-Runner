## Context

当前主规格里同时存在共享 capability 与 qwen engine-specific capability 两种模式。`engine-auth-qwen`、`qwen-stream-parser`、`qwen-ui-shell-security` 记录的其实不是“qwen 独有架构”，而是 qwen 在共享 auth、parser、UI shell 安全框架下的具体实例。相比 `claude`、`opencode` 等已归并到共享 spec 的做法，这三份 spec 让 capability 边界显得不一致，也让后续新增引擎时更容易沿用“先建一个 engine-specific spec”这种模式。

这个 change 的目标不是改代码行为，而是整理规范层次：把 qwen 的实例化要求放回共享 capability，把三个 qwen 专属 capability 从主规格中退场。

## Goals / Non-Goals

**Goals:**
- 为 qwen auth / parser / UI shell security 找到与现有项目风格一致的共享 capability 归宿。
- 在共享 specs 中保留 qwen 的必要规范要求，避免因为 capability 移除而丢失行为约束。
- 让后续 change 可以继续向共享 capability 写增量，而不是向 qwen 专属 capability 追加新需求。

**Non-Goals:**
- 不改变当前 qwen 的实现行为、对外 API 或运行时协议。
- 不在这次 change 中重构其它 engine-specific capability。
- 不同步归档或删除实际代码文件；这里只定义后续 sync/archive 的规范基础。

## Decisions

### 1. 用“共享 capability + qwen 场景”替代 qwen 专属 capability

保留 qwen 的要求，但把它们写成共享 capability 下的 engine-specific scenario，而不是继续维持独立 capability。这样可以保持 capability 语义按领域组织，而不是按 engine 名称组织。

备选方案：
- 保留现有 qwen 专属 capability，只在 Purpose 中说明它们是过渡性文档。
  - 不采用，因为这会继续允许后续 change 往这些 capability 写新 delta，问题不会真正收口。

### 2. parser 要求拆到 runtime contract 与 run observability，而不是维持单独 parser capability

`qwen-stream-parser` 里有两类内容：一类是 adapter 必须提供什么解析能力，另一类是 live/RASP 该如何观察这些语义。前者属于 `engine-adapter-runtime-contract`，后者属于 `interactive-run-observability`。

备选方案：
- 全部并到 `engine-adapter-runtime-contract`。
  - 不采用，因为 `run_handle`、`agent.tool_call`、`agent.command_execution` 这些已经是 observability/协议层责任，不应全部塞回 adapter contract。

### 3. UI shell 安全要求拆到 inline terminal、runtime contract 与 config layering

`qwen-ui-shell-security` 同时覆盖了：
- UI shell session 行为与限制
- adapter profile 中的 config asset 声明
- session-local config 的分层合成

这些分别落在：
- `ui-engine-inline-terminal`
- `engine-adapter-runtime-contract`
- `engine-runtime-config-layering`

备选方案：
- 把全部内容并入 `ui-engine-inline-terminal`。
  - 不采用，因为 profile 资产声明与 config layering 不是纯 UI 行为。

### 4. 用 REMOVED delta 显式退役三个 qwen capability

为了避免 capability 目录继续存在并被误用，这次 change 要为 `engine-auth-qwen`、`qwen-stream-parser`、`qwen-ui-shell-security` 写 REMOVED delta，并给出迁移目标。

备选方案：
- 只修改共享 specs，不写 removal delta，后续人工删目录。
  - 不采用，因为这会让“为什么能删”和“删完迁移去哪”缺少规范化依据。

## Risks / Trade-offs

- [Risk] 共享 spec 与 qwen 现有行为的映射不完整，导致 removal 后有约束丢失。 → Mitigation: 在共享 specs 里只迁移仍然有效、可执行的要求，并在 removal delta 中给出明确 migration 指向。
- [Risk] 归并后共享 specs 中出现过多 qwen-specific 细节，降低可读性。 → Mitigation: 只保留必要的 qwen scenario，不把实现笔记和历史过渡语义也一并搬过去。
- [Risk] 后续 sync/archive 顺序错误，导致主 specs 与 archived change 不一致。 → Mitigation: tasks 中显式列出“先补 shared delta，再移除 engine-specific capability”的顺序与校验步骤。

## Migration Plan

1. 为共享 capability 编写 delta specs，先让 qwen 的要求在共享 specs 中有落点。
2. 为三个 qwen engine-specific capability 编写 REMOVED delta，声明 Reason 和 Migration。
3. 在实现/同步阶段将 delta 同步进主 specs。
4. 校验没有后续 active change 继续依赖这三个 qwen capability 后，再归档并从主规格中移除。

## Open Questions

- 是否还有其它 engine-specific capability 也应按同样模式并回共享 specs？这不阻塞本 change，但可以在完成本轮后继续做一次全局清理审计。
