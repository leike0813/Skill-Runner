## Why

当前执行体系存在“常规链路（`/v1/jobs`）”与“临时 skill 链路（`/v1/temp-skill-runs`）”两套实现。  
两条链路在创建请求、上传触发、调度执行、状态读取、日志/事件读取、产物读取、取消等方面存在大量重复逻辑，导致：

- 变更成本高：同一策略（如 timeout/cache/观察协议）需要双份修改；
- 演进风险高：两条链路容易发生行为漂移；
- 测试成本高：回归矩阵扩大且难以保持一致。

需要通过一次架构级重构，明确“必须独立”与“可以共用”的边界，并建立统一核心执行层。

## What Changes

- 新增双链路统一执行架构规范（Run Source 架构）：
  - 明确 `installed` 与 `temp` 两种 source 的职责边界；
  - 提炼共用执行核心（校验、调度、观测读取、取消、缓存策略）；
  - 保留 source 独立能力（skill 获取与生命周期、存储命名空间）。
- 明确双链路能力同构要求：`pending/reply/history/range` 在常规链路与临时链路 MUST 保持一致语义与可用性。
- 在不改变现有外部 API 路径与调用方式的前提下，重构后端内部路由实现，减少重复代码。
- 输出能力矩阵（独立/共用），作为后续功能演进的约束基线。

## Capabilities

### New Capabilities
- `dual-run-chain-architecture`: 定义双链路统一执行核心与 source 独立边界。

### Modified Capabilities
- `interactive-job-api`: 内部执行链路改为复用统一核心服务。
- `ephemeral-skill-upload-and-run`: 内部执行链路改为复用统一核心服务，并保留临时 skill 专属职责。
- `management-api-surface`: 对 run 读路径的能力矩阵与 source 差异作显式规范。

## Impact

- Affected code (expected):
  - `server/routers/jobs.py`
  - `server/routers/temp_skill_runs.py`
  - `server/services/*`（新增或重构统一执行核心服务）
  - `tests/unit/*`（双链路一致性与差异性测试）
  - `tests/api_integration/*` 与 `tests/engine_integration/*`（双链路回归）
- Affected APIs:
  - 外部路径保持不变（兼容现有调用）。
  - 仅内部实现与一致性行为规范调整。
- Affected docs:
  - 变更文档与相关开发文档（执行架构/能力矩阵）。
