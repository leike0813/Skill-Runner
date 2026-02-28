## Why

当前鉴权与执行适配实现存在两个结构性问题：
1. 鉴权 transport（`oauth_proxy`/`cli_delegate`）与 engine-specific 逻辑混杂，`EngineAuthFlowManager` 承担过多职责。
2. `server/adapters/*` 单类体积持续膨胀，配置、环境、命令、解析、会话句柄等逻辑耦合，新增引擎成本高。

本 change 目标是在不破坏现有 API 的前提下，完成“按引擎聚合 + transport 内核化 + adapter 组件化”的 phase1 重构。

## What Changes

1. 建立 `server/engines/<engine>/` 纵向聚合目录，收敛该引擎的 `adapter` 与 `auth` 实现。
2. 建立 `server/runtime/auth` 与 `server/runtime/adapter` 公共内核层，承载 transport 与 adapter 契约。
3. `EngineAuthFlowManager` 降级为 façade；transport orchestrator 不再包含 engine-specific 分支。
4. `EngineAdapterRegistry` 切换到引擎包入口注册；旧 `server/adapters/*` 保留桥接导入。
5. 对外 `/v1` 与 `/ui` 鉴权接口保持兼容。

## Scope

### In Scope

1. 新目录骨架与核心契约文件落地。
2. 四引擎（codex/gemini/iflow/opencode）的 adapter/auth 入口迁移到 `server/engines/*`。
3. 旧路径保留兼容桥接，确保现有调用与测试可继续运行。
4. transport orchestrator 的引擎分支下沉到 driver capability 层。

### Out of Scope

1. 不新增鉴权 provider 能力。
2. 不变更对外 HTTP API 路径与核心语义。
3. 本 phase 不删除旧模块文件，仅桥接与迁移接线。

## Success Criteria

1. engine-specific 代码可在 `server/engines/<engine>/` 定位。
2. transport orchestrator 中无 engine-specific `if engine == ...` 分支。
3. adapter 具备统一组件契约，且 `EngineAdapterRegistry` 通过引擎包入口装配。
4. 鉴权与适配相关现有测试通过，接口行为不回归。
