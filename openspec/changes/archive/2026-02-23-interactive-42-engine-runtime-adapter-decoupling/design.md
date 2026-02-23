## Context

当前系统中存在两条与引擎执行相关的路径：  
1) 主服务通过 `job_orchestrator -> adapter.run` 执行；  
2) 外挂 Harness 直接拼接引擎命令并独立处理部分解析。  

这导致命令参数来源和解析来源不一致，回归验证与线上行为可能偏离。与此同时，运行中消息协议（RASP/FCMP）中的引擎特定解析逻辑仍集中在通用服务层，导致跨引擎扩展与维护成本上升。

## Goals / Non-Goals

**Goals:**
- 定义统一的 Adapter 运行时接口，覆盖 start/resume 命令构建与 runtime 流解析。
- 将引擎特定解析逻辑迁移到各引擎 Adapter，通用协议层保持引擎无关。
- 通过配置文件提供 API 链路命令默认参数 Profile。
- 保持 Harness 参数策略为“纯透传驱动”，不注入 Profile 默认值。
- 引入临时 `opencode` Adapter 承接可迁移解析逻辑，并对未实现执行能力显式降级。

**Non-Goals:**
- 本 change 不新增 HTTP API 路径。
- 本 change 不实现 `opencode` 完整执行适配能力。
- 本 change 不重写 RASP/FCMP 事件协议字段本身（仅调整解析来源与调用边界）。

## Decisions

### Decision 1: 抽象 Adapter Runtime Interface 作为唯一引擎接入点

新增（或扩展）Adapter 通用接口，至少包含：
- start 命令构建；
- resume 命令构建；
- runtime 流解析输出（标准化字段）。

主服务与 Harness 均通过该接口调用，引擎行为不再由多个位置重复实现。

**Why this over keeping harness-specific command builder**
- 避免命令构建分叉导致的参数漂移；
- 降低新增引擎或调整引擎参数时的重复修改面。

### Decision 2: 引擎特定 runtime 解析全迁移到 Adapter

`runtime_event_protocol` 不再持有 codex/gemini/iflow/opencode 的专用解析分支，仅负责：
- 读取原始日志；
- 调用 Adapter 的解析结果；
- 构建 RASP/FCMP 事件与通用去重/度量。

**Why this over partial migration**
- 全迁移边界更清晰，后续不会继续把引擎逻辑回灌到通用层；
- 可直接用 Adapter 契约约束新增引擎行为。

### Decision 3: Profile 仅用于 API 链路默认参数

新增 `server/assets/configs/engine_command_profiles.json`，仅在后端 API 执行链路注入默认参数。  
Harness 不读取 Profile，命令参数只来自用户透传与必要恢复上下文（session handle/message）。

**Why this over shared profile for harness**
- Harness 目标是做参数敏感与一致性验证，默认参数注入会掩盖真实透传行为；
- 满足“后端默认值策略”与“夹具可控输入”两类需求分离。

### Decision 4: `opencode` 使用临时 Adapter 占位

创建临时 `opencode` Adapter：
- 先承接 runtime 流解析能力；
- 执行命令构建/实际执行未实现部分返回结构化 capability unavailable。

**Why this over deferring opencode completely**
- 允许先完成接口与迁移闭环，避免后续再次重构通用层；
- 保留明确扩展点并减少未来冲击面。

## Risks / Trade-offs

- [风险] 接口迁移期间，主服务与 Harness 调用路径都在变化，容易出现行为回归  
  → Mitigation: 增加针对命令构建、解析输出与事件组装的一致性单元测试与夹具测试。

- [风险] Profile 规则与透传规则冲突导致参数优先级混乱  
  → Mitigation: 明确 API 链路与 Harness 链路的合并策略并在规范中写为 MUST。

- [风险] `opencode` 占位 Adapter 被误解为完整支持  
  → Mitigation: 统一错误码与文档标注 capability-gated 状态。

- [风险] 解析迁移后 FCMP 去重行为发生变化  
  → Mitigation: 保持去重逻辑留在通用层，并用回归样本锁定输出期望。

## Migration Plan

1. 扩展 Adapter 基类/接口，定义统一命令构建与 runtime 解析契约。
2. 将 codex/gemini/iflow 的 runtime 解析从通用服务迁入各 Adapter。
3. 新增临时 `opencode` Adapter 并接入同一契约。
4. 改造 `runtime_event_protocol` 为“读取日志 + 调用 Adapter 解析 + 事件组装”。
5. 新增命令 profile 配置与加载逻辑，并仅在 API 编排链路注入。
6. 改造 Harness 调用共享 Adapter 命令构建与解析，移除直拼命令路径。
7. 增加单元测试与一致性测试，完成 OpenSpec verify。

## Open Questions

- 无阻塞问题；当前关键决策均已确认，可直接进入实现。
