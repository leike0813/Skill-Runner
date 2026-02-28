## Architecture Intent

本次采用中度解耦：保留 runtime 与 orchestration 的协作，但通过显式端口收束依赖方向。

### Runtime 职责

- 运行期协议、状态机、会话生命周期、日志物化与解析。
- 不直接依赖 orchestration 单例。

### Orchestration 职责

- 业务编排与系统接入（store、workspace、job、route 组装）。
- 为 runtime 提供 ports 的具体实现。

## Key Design Decisions

1. `runtime/execution` 归位到 `services/orchestration`：
   - `run_execution_core.py`
   - `run_interaction_service.py`
2. `runtime/observability` 通过 contracts 注入：
   - `RunStorePort`
   - `WorkspacePort`
   - `JobBundlePort`
3. `runtime/protocol` 通过 `RuntimeParserResolverPort` 注入 parser 解析能力。
4. 路由层负责安装端口（bootstrap），runtime 不感知 orchestration 单例。

## Dependency Direction

### Allowed

- `server/services/orchestration/*` -> `server/runtime/*`
- `server/runtime/*` -> `server/runtime/*`

### Forbidden

- `server/runtime/*` -> `server/services/orchestration/*`

## Runtime/Orchestration Bridge

新增桥接模块：

- `server/services/orchestration/runtime_observability_ports.py`
- `server/services/orchestration/runtime_protocol_ports.py`

桥接模块负责把 orchestration 单例组装为 runtime 端口，并在路由初始化时安装。
