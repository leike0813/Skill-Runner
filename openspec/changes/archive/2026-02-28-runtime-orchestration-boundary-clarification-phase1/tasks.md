## 1. OpenSpec

- [x] 1.1 创建 `runtime-orchestration-boundary-clarification-phase1` 工件与 delta specs
- [x] 1.2 `openspec validate runtime-orchestration-boundary-clarification-phase1 --type change`

## 2. Runtime Ownership

- [x] 2.1 将 `runtime/execution/run_execution_core.py` 迁移到 `services/orchestration`
- [x] 2.2 将 `runtime/execution/run_interaction_service.py` 迁移到 `services/orchestration`
- [x] 2.3 路由导入切换到 `services/orchestration` 并删除 runtime/execution 业务文件

## 3. Observability Ports

- [x] 3.1 新增 `runtime/observability/contracts.py`
- [x] 3.2 `runtime/observability/*` 移除 orchestration 单例直接导入
- [x] 3.3 新增 orchestration 端口安装模块并在路由初始化时注入

## 4. Protocol Parser Resolver

- [x] 4.1 新增 `runtime/protocol/contracts.py`
- [x] 4.2 `runtime/protocol/event_protocol.py` 改为 resolver port 注入
- [x] 4.3 新增 orchestration resolver 端口安装模块

## 5. Validation

- [x] 5.1 新增/更新测试覆盖端口注入和边界守卫
- [x] 5.2 关键回归测试通过
- [x] 5.3 mypy 通过
