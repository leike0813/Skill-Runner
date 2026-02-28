## Why

当前 `runtime` 与 `services/orchestration` 的边界对开发者不够直观，主要体现在：

1. `runtime/execution` 承载了业务编排逻辑。
2. `runtime/observability` 直接依赖 orchestration 单例。
3. `runtime/protocol/event_protocol.py` 直接依赖 `engine_adapter_registry`。

这会导致目录语义和依赖方向不一致，增加维护与演进成本。

## What Changes

1. 将 `runtime/execution` 两个业务编排模块迁回 `services/orchestration`。
2. 为 `runtime/observability` 引入端口契约，去除对 orchestration 单例的直接导入。
3. 为 `runtime/protocol` 引入 parser resolver 端口，去除对 `engine_adapter_registry` 直连。
4. 对外 API 与 UI 行为保持兼容，仅做内部边界收口。

## Scope

### In Scope

- `runtime/execution` 所有权归位。
- `runtime/observability` 端口注入改造。
- `runtime/protocol` parser resolver 端口改造。
- 相关路由接线与测试补充。

### Out of Scope

- 不新增业务能力。
- 不变更 `/v1` 与 `/ui` 对外契约。
- 不追求 runtime 与 orchestration 完全解耦。

## Success Criteria

1. `runtime` 不再直接 import `server.services.orchestration.*`。
2. `runtime/execution` 不再承载业务编排实现文件。
3. 观测与协议解析通过 ports/contracts 与 orchestration 交互。
4. 关键回归测试通过，行为无回归。
