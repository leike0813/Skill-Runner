## Architecture Overview

### 1) Directory Verticalization

新增目录：
1. `server/engines/codex/{adapter,auth}`
2. `server/engines/gemini/{adapter,auth}`
3. `server/engines/iflow/{adapter,auth}`
4. `server/engines/opencode/{adapter,auth}`
5. `server/runtime/auth/*`
6. `server/runtime/adapter/*`

规则：
1. engine-specific 逻辑不再新增到 `server/services/*` 和 `server/adapters/*`。
2. `server/services/*` 仅保留 orchestration、façade、router-facing 组合逻辑。

### 2) Auth Transport Core

目标：
1. transport 层只处理会话生命周期、锁、状态机、日志与输入分发。
2. engine-specific 能力判断与执行由 driver 层负责。

实现：
1. `server/runtime/auth/contracts.py` 定义 `AuthDriverContext`、`AuthDriverResult`。
2. `server/runtime/auth/driver_registry.py` 支持 capability 查询与 driver 对象注册。
3. `server/services/auth_runtime/orchestrators/*` 改为依赖 capability resolver，不写引擎分支。

### 3) Adapter Component Contracts

`server/runtime/adapter/contracts.py` 定义组件接口：
1. `ConfigComposer`
2. `WorkspaceProvisioner`
3. `PromptBuilder`
4. `CommandBuilder`（start/resume）
5. `StreamParser`
6. `SessionHandleCodec`

`server/runtime/adapter/base_execution_adapter.py` 提供统一生命周期编排容器（phase1 先作为契约容器，不要求一次性替换全部细节实现）。

### 4) Compatibility Strategy

1. 保留 `server/adapters/*` 文件，内部转调 `server/engines/*/adapter/entry.py`。
2. 保留现有 `server/services/*_auth_*` 对外可见导入路径，内部转调 `server/engines/*/auth/*`。
3. `engine_auth_flow_manager` 与 router 接口保持不变，只重组内部装配来源。

### 5) Risk Controls

1. 迁移采用“文件就位 + 入口切换 + 兼容桥接”三步，不做直接删除。
2. 每次切换后跑对应单元测试（adapter/auth 分别覆盖）。
3. Driver capability 的约束来源收敛到单处，避免 UI 与后端矩阵漂移。
