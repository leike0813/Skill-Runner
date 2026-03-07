## Why

当前容器启动阶段（entrypoint -> agent ensure -> 模型探测）在失败时只输出简短的 `exit=1`，缺少失败命令、stderr 摘要、耗时与阶段信息，导致定位问题成本高。  
典型表现是 API 已启动但 agent CLI 缺失，后续触发 `opencode CLI not found`，排障只能进容器手工搜线索。

## What Changes

- 为容器启动阶段引入结构化阶段日志（stdout + 持久化文件双写）。  
- 为 `agent_manager --ensure` 增加每引擎安装结果详情（命令、耗时、stderr 摘要、建议）。  
- 生成启动诊断工件（例如 `agent_bootstrap_report.json`），便于复盘。  
- 为 opencode 模型探测失败补充“依赖未安装”指向信息，避免二次猜测。  
- 文档补充容器启动排障路径和日志位置。

## Capabilities

### New Capabilities

- `local-deploy-bootstrap`: 容器启动阶段可输出可追溯的安装/探测诊断日志。

### Modified Capabilities

- `logging-persistence-controls`: 增加“启动期诊断日志”工件与开关策略（默认开启，支持大小轮转）。

## Impact

- Affected code:
  - `scripts/entrypoint.sh`
  - `scripts/agent_manager.py`
  - `server/services/engine_management/agent_cli_manager.py`
  - `server/engines/opencode/models/catalog_service.py`
  - `docs/containerization.md`
- API impact: None.
- Runtime protocol impact: None.
