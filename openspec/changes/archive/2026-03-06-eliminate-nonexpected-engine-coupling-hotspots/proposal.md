# Change Proposal: eliminate-nonexpected-engine-coupling-hotspots

## 背景
`artifacts/engine_coupling_analysis_2026-03-06.md` 显示当前系统在 runtime/orchestration/ui/platform 主干中仍存在多处非预期 engine-specific 分支（`if engine == ...`），导致新增引擎时改动面过大、跨层扩散明显。

当前问题主要集中在：
- `ui_shell_manager.py`：命令参数、sandbox 探测、安全配置、鉴权提示均为硬编码分支
- `cache_key_builder.py`：引擎配置文件名泄漏到平台层
- `job_orchestrator.py` / `run_filesystem_snapshot_service.py`：工作目录与忽略规则硬编码
- `main.py` / `routers/ui.py` / `model_registry.py`：opencode model catalog 生命周期特判
- `runtime/auth_detection/service.py`：直接 import 各引擎 detector
- `agent_cli_manager.py`：安装包/二进制名/凭据规则/resume 探测参数仍以内置常量和局部分支维护

## 目标
- 一次性收口“非预期耦合”（全覆盖），保留“预期内 registry/data-driven 耦合”不动。
- 将 engine-specific 决策下沉到 engine 能力层或统一策略接口。
- 在不改变外部 API 与协议语义前提下，减少新增引擎的横向修改文件数。
- 继续收口 engine management 内“非必要硬编码”：将 CLI 管理声明迁入 `adapter_profile` 并由声明式策略执行。

## 非目标
- 不改 FCMP/RASP 协议语义与状态机语义。
- 不删除 engine management 域内集中注册点（adapter/driver registry）。
- 不做对外破坏式 API 删除（保留 opencode model refresh 兼容入口）。
