## Context

当前双链路的重复点主要集中在：

- 请求创建阶段：runtime/model/options 校验、执行模式校验、缓存策略判定；
- 上传触发阶段：输入清单生成、cache key 计算、调度入队；
- run 读路径：状态、日志、事件流、结果、产物、bundle、取消；
- 错误映射与状态写回：大量重复的异常处理与状态更新逻辑。

与此同时，两条链路也存在不可简单合并的差异：

- skill 来源不同（已安装 skill vs 上传临时包）；
- 生命周期管理不同（临时包 staging/清理）；
- 存储命名空间不同（常规 cache 与临时 cache 已分表）；
- 当前交互能力实现存在差异（pending/reply/history/range），需在本 change 内完成同构。

## Goals / Non-Goals

**Goals**

- 通过统一核心执行层显著减少双链路重复代码。
- 明确并固化“独立职责 vs 共用职责”的边界，避免未来再次耦合。
- 保持现有外部 API 兼容（路径、基本语义、调用流程不破坏）。
- 实现双链路 `pending/reply/history/range` 能力与语义同构。

**Non-Goals**

- 不在本次 change 中合并外部 API 路由。
- 不重写现有数据模型为单表（保留现有命名空间隔离策略）。

## 独立 / 共用分析

### 必须保持独立（Source-specific）

1. Skill 获取与装载
- `installed`: 由 `skill_id` 从 registry 解析。
- `temp`: 由上传包解压、校验、stage 后得到 skill。

2. 临时 skill 生命周期
- 仅 `temp` 需要 package/staged 目录创建与终态清理策略。

3. 存储命名空间
- request/run 元数据读取入口不同；
- cache 表保持隔离（常规与临时分开），避免跨链路误命中。

### 应当共用（Shared core）

1. 运行选项与模型校验
- runtime options、execution mode、model registry 校验流程统一。

2. 调度执行与并发控制
- 并发 admit/reject、job_orchestrator 调用、取消流程框架统一。

3. 输入清单与缓存策略
- auto-only cache 策略统一；
- cache key 组装流程统一（source 扩展因子由 source adapter 提供）。

4. run 读路径框架
- 状态、日志、事件流、结果、产物、bundle 的读取流程统一；
- source adapter 负责具体路径差异与能力开关。

5. 错误映射与状态回写
- 统一错误分类、HTTP 映射与状态落盘策略。

6. 交互与历史能力
- `pending/reply/history/range` 的执行语义、状态约束与错误映射统一；
- 两条链路使用同一套核心能力实现，不允许分叉逻辑。

## Decisions

### Decision 1: 引入 Run Source 抽象层

定义 `RunSourceAdapter`（`installed`/`temp` 两实现）：

- 提供 source 专属能力：
  - skill 解析方式；
  - request/run 记录读取与写入；
  - cache namespace；
  - source 扩展 cache 因子（如 temp 包 hash）；
  - 能力标记（是否支持 pending/reply/history/range）。

### Decision 2: 提炼统一执行核心服务

拆分并复用如下核心流程：

- `ExecutionCreateService`: create 阶段通用校验与 request 初始化；
- `ExecutionUploadStartService`: upload 后的 manifest/cache/schedule 通用流程；
- `RunReadFacade`: 状态/日志/事件/结果/产物/bundle/取消统一入口；
- `ExecutionErrorPolicy`: 统一异常转 HTTP 与状态更新。

### Decision 3: 外部 API 保持双入口，内部走同一核心

- `/v1/jobs*` 与 `/v1/temp-skill-runs*` 路由保留；
- 路由层仅负责 source 绑定与参数映射；
- 业务逻辑收敛到统一核心服务 + source adapter。

### Decision 4: 通过能力矩阵显式管理差异

定义 source 能力矩阵（示例）：

- supports_pending_reply
- supports_event_history
- supports_log_range
- supports_inline_input_create

统一由 adapter 暴露，避免在路由中散落分支判断。
其中 `supports_pending_reply / supports_event_history / supports_log_range` 对 `installed` 与 `temp` MUST 同时为 `true`，作为本次重构验收约束。

### Decision 5: 以统一交互服务实现双链路同构能力

新增统一交互与历史服务面（建议）：

- `InteractionService`: pending 查询与 reply 提交；
- `EventHistoryService`: 事件历史区间读取；
- `LogRangeService`: 日志区间读取；

`jobs.py` 与 `temp_skill_runs.py` 仅做 source 绑定与参数转换，业务语义必须一致。

## Risks / Trade-offs

- [风险] 重构期间回归面大  
  → Mitigation: 先建立“行为对齐快照测试”，再逐段替换实现。

- [风险] 过度抽象导致可读性下降  
  → Mitigation: 仅抽取被双链路重复调用的稳定流程，避免提前泛化。

- [风险] source 边界定义不清导致职责回流  
  → Mitigation: 用能力矩阵 + adapter 接口强约束边界。

## Migration Plan

1. 在 specs 中落地“独立/共用”规范与能力矩阵约束。
2. 新增 `RunSourceAdapter` 接口与 `installed/temp` 实现。
3. 提炼 create/upload/start 共用流程，替换两个 router 重复逻辑。
4. 提炼 run read facade，统一状态/日志/事件/结果读取路径。
5. 提炼并接入统一交互/历史服务，补齐 temp 链路 `pending/reply/history/range`。
6. 以对等测试矩阵验证两链路能力同构与语义一致。
7. 补齐单测与集成回归，确保 API 行为兼容。
