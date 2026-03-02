## Context

`JobOrchestrator` 在 wave1 后已完成 bundle/snapshot/audit/interaction/recovery 职责拆分，但 `run_job` 仍承载完整生命周期实现，导致：
- 变更触达面过大；
- 单测 patch 成本高（大量依赖 `job_orchestrator` 模块路径）；
- 编排逻辑可读性与可维护性仍偏弱。

本波只处理 `run_job` 主流程下沉，保持行为兼容与低风险迁移。

## Goals / Non-Goals

**Goals**
- 将 `run_job` 主生命周期迁移到新服务 `RunJobLifecycleService`。
- `JobOrchestrator.run_job` 收敛为薄委派入口。
- 保持对外接口、runtime 合同与当前状态机行为不变。

**Non-Goals**
- 不重构 `cancel_run` 与 recovery 主入口架构。
- 不修改 HTTP API 与 runtime schema/invariants。
- 不进行大规模测试重写，仅必要适配。

## Decisions

### 1) 新增 RunJobLifecycleService 承载主流程
- 新文件：`run_job_lifecycle_service.py`
- 新增 dataclass：
  - `RunJobRequest`
  - `RunJobRuntimeState`
  - `RunJobOutcome`
- `run` 方法接收 `orchestrator` 上下文与 `RunJobRequest`，复用现有 helper/wrapper 以保持兼容。

### 2) 保持 JobOrchestrator 的稳定外观
- `JobOrchestrator.run_job` 仅构造 `RunJobRequest` 并委派执行。
- `OrchestratorDeps` 新增 `run_job_lifecycle_service` 注入点，默认装配新服务。
- 现有兼容 helper/wrapper 不删除，继续由 orchestrator 暴露。

### 3) 低风险迁移方式
- 首先保持逻辑等价迁移（尽量不改变控制流）。
- 不改变路由/port 调用点与模块级单例 `job_orchestrator`。
- 对测试 patch 路径保持兼容：尽量继续通过 `job_orchestrator` 模块级对象生效。

## Risks / Trade-offs

- [Risk] 迁移 run_job 过程中引入行为漂移。  
  → Mitigation: 采用“等价搬运 + 必跑回归”策略，严格以当前测试矩阵验证。

- [Risk] helper/wrapper 绑定关系变化导致测试失效。  
  → Mitigation: 保留 orchestrator 原有代理方法与调用路径，不强制测试重构。

## Migration Plan

1. 创建 wave2 OpenSpec artifacts（delta spec）。
2. 新增 `RunJobLifecycleService` 与 request/state/outcome 类型。
3. 将 `run_job` 主流程迁移到新服务。
4. 收敛 orchestrator 的 `run_job` 为薄委派入口。
5. 更新 docs 并执行回归测试 + runtime 必跑清单 + mypy。
