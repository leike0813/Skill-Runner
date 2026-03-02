## Context

当前 `JobOrchestrator` 体量过大且跨职责实现，包含执行生命周期、交互恢复、审计落盘、bundle 打包、文件系统快照、重启恢复等逻辑。该结构导致测试需要大量 monkeypatch 模块级单例，也增加了新增行为和修复缺陷时的耦合风险。  
本次重构需要满足“行为不变、接口兼容、可分阶段回滚”的工程约束，并与现有 FCMP/RASP 合同及状态机语义保持一致。

## Goals / Non-Goals

**Goals:**
- 将 `JobOrchestrator` 收敛为薄协调器，核心职责为 run 生命周期编排。
- 抽离 5 个职责组件：bundle、filesystem snapshot、audit、interaction lifecycle、restart recovery。
- 引入稳定内部端口 `JobControlPort`，改善 runtime observability 与 orchestrator 的耦合方式。
- 保持现有外部 API、运行时协议、状态转换和文件产物语义不变。

**Non-Goals:**
- 不进行 SQLite 异步化改造。
- 不改动 runtime schema / invariants 内容。
- 不在本次中移除 `job_orchestrator` 模块级单例。
- 不扩展新功能（仅结构重构与兼容增强）。

## Decisions

### 1) 采用“薄协调器 + 组件服务”的组合架构
- Decision: 新增 `RunBundleService`、`RunFilesystemSnapshotService`、`RunAuditService`、`RunInteractionLifecycleService`、`RunRecoveryService`。
- Rationale: 明确职责边界，降低单类复杂度并提高局部可测性。
- Alternative considered:
  - 保持单文件，仅按 region 整理方法。被否决：无法降低耦合和测试 patch 成本。

### 2) 通过 `OrchestratorDeps` 聚合依赖并支持可注入测试替身
- Decision: 在 `JobOrchestrator.__init__` 接受可选 `deps`，默认绑定现有单例；测试可注入 fake backend。
- Rationale: 逐步减少对 `patch("...job_orchestrator.run_store", ...)` 的强耦合。
- Alternative considered:
  - 全量迁移 FastAPI Depends。被否决：改动面过大，超出本次重构边界。

### 3) 新增 `JobControlPort.build_run_bundle` 并保留 `_build_run_bundle` 兼容层
- Decision: `run_read_facade` 优先调用 `build_run_bundle`，回退 `_build_run_bundle`。
- Rationale: 在不破坏现有伪实现/测试替身的情况下建立稳定接口。
- Alternative considered:
  - 直接替换全部 `_build_run_bundle` 调用。被否决：一次性修改风险高，影响现有测试假对象。

### 4) 分阶段迁移，先纯 I/O 再状态敏感逻辑
- Decision: 先抽 bundle/snapshot，再抽 audit，再抽 interaction/recovery，最后瘦身主流程。
- Rationale: 优先迁移副作用较可控逻辑，降低状态机相关回归风险。
- Alternative considered:
  - 一次性重写 `run_job`。被否决：验证和回滚成本过高。

## Risks / Trade-offs

- [Risk] 组件拆分后参数传递复杂度上升。  
  → Mitigation: 通过具名参数和小型 dataclass/typed dict 限定入参，保持调用清晰。

- [Risk] 测试仍大量依赖旧私有方法名。  
  → Mitigation: 迁移期保留兼容包装方法（如 `_build_run_bundle`），并逐步更新测试断言目标。

- [Risk] 交互恢复和 auto-decide 流程改动易出现状态回归。  
  → Mitigation: 保留原状态机分支与错误码语义，先复用原逻辑再搬移代码，完成后跑完整回归测试。

- [Risk] runtime observability 端口变更影响注入测试。  
  → Mitigation: 接口设计采用“新接口优先 + 旧接口回退”策略，保障旧假对象仍可运行。

## Migration Plan

1. 创建并提交 OpenSpec change artifacts（proposal/specs/design/tasks）。
2. 新增组件服务文件并从 `JobOrchestrator` 迁移对应逻辑（保持行为一致）。
3. 修改 `JobOrchestrator` 组装组件并保留兼容包装方法。
4. 修改 observability job-control 侧调用新接口并保留回退。
5. 更新并通过 orchestrator 相关单测。
6. 若回归失败，按组件粒度回滚对应阶段（优先回滚 interaction/recovery，再回滚 audit，再回滚 bundle/snapshot）。

## Open Questions

- 无阻塞性开放问题。本次设计按兼容优先落地，可直接实施。
