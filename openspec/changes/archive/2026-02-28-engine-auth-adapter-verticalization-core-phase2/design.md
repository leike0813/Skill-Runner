## Design Overview

phase2 目标是把“目录重构”变成“可持续扩展的工程结构”。

### 1) Runtime Auth Core（engine-agnostic）

主实现位于 `server/runtime/auth/`：
1. `driver_registry.py`：按 `(transport, engine, auth_method, provider_id)` 注册能力与元信息。
2. `session_store.py`：会话索引、活动会话定位。
3. `log_writer.py`：按 transport 分离日志目录与路径。
4. `callback_router.py`：统一 callback 参数解析、错误映射、页面渲染。
5. `orchestrators/*.py`：transport 级 façade，补充 `transport_state_machine/orchestrator` 观测字段。

约束：
1. transport 模块不直接承载 engine-specific 协议实现。
2. `waiting_orchestrator` 仍仅属于 `cli_delegate` 语义，不进入 `oauth_proxy` 状态机。

### 2) Engine Verticalization

每个引擎统一目录：
1. `server/engines/<engine>/adapter/*`
2. `server/engines/<engine>/auth/*`

其中：
1. `adapter/adapter.py` 保留引擎执行核心实现。
2. `adapter/{config_composer,workspace_provisioner,prompt_builder,command_builder,stream_parser,session_codec}.py` 作为标准组件层。
3. `auth/protocol/*` 承载 OAuth/device 等协议语义。
4. `auth/drivers/*` 承载 CLI delegate 流程。
5. `auth/callbacks/*` 承载引擎专属 callback listener。

### 3) Adapter Runtime Contracts

`server/runtime/adapter/contracts.py` 固化 6 组件契约：
1. `ConfigComposer`
2. `WorkspaceProvisioner`
3. `PromptBuilder`
4. `CommandBuilder`
5. `StreamParser`
6. `SessionHandleCodec`

`server/runtime/adapter/base_execution_adapter.py` 作为统一编排容器，`entry.py` 负责组件装配。

### 4) Compatibility Plan

1. 对外 API 路由保持不变：`/v1/engines/auth/*` 与 `/ui/engines/auth/*`。
2. `EngineAuthFlowManager` 继续承担 façade 与兼容层职责，内部导入转向 `server/runtime/*` 与 `server/engines/*`。
3. 旧桥接实现文件删除，不再作为运行路径。

### 5) Risks & Mitigations

1. 风险：迁移后导入路径断裂。
   - 控制：全局 `rg` 检查 + 关键测试集覆盖。
2. 风险：adapter 相对导入层级错误。
   - 控制：mypy + 四引擎 adapter 测试。
3. 风险：callback listener patch 路径漂移。
   - 控制：`test_engine_auth_flow_manager.py` 中 listener mock 回归覆盖。
