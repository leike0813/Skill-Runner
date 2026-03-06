# Design: eliminate-nonexpected-engine-coupling-hotspots

## 设计原则
- 保留“集中注册点耦合”，清理“业务主干分支耦合”。
- 统一通过能力提供器/生命周期注册器访问 engine-specific 行为。
- 兼容优先：对外接口不破坏，内部改为策略驱动。

## 关键决策

### 1) UI Shell 能力提供器
新增 `EngineShellCapabilityProvider`，为 `ui_shell_manager` 提供：
- `launch_args`
- `sandbox_probe_strategy`
- `session_security_strategy`
- `auth_hint_strategy`

`ui_shell_manager` 不再包含 per-engine 逻辑分支，仅负责流程编排和错误回滚。

### 2) cache_key_builder 配置路径收敛
`compute_skill_fingerprint()` 改为读取 adapter profile 的
`config_assets.skill_defaults_path`，不再硬编码每个引擎的默认配置文件名。

### 3) orchestrator/filesystem 轻度耦合收口
- `job_orchestrator` 从 adapter profile 读取 `attempt_workspace.workspace_subdir`。
- `run_filesystem_snapshot_service` 的忽略目录集合改为由 engine profile 动态生成。
- `run_folder_trust_manager` 不再在 orchestrator 层硬编码 codex/gemini 默认路径，路径解析下沉到 trust registry 层。

### 4) model catalog 生命周期抽象
新增 `EngineModelCatalogLifecycle`：
- 统一 `start/stop/refresh/request_refresh_async/get_snapshot/cache_paths`
- `main.py`、`routers/ui.py`、`model_registry.py` 不再直接依赖 `opencode_model_catalog`
- 对外仍保留 `/ui/engines/opencode/models/refresh` 兼容入口，内部走生命周期注册器

### 5) 其余非预期耦合
- `runtime/auth_detection/service.py` 使用 detector registry 注入，不再直接 import 每个 detector。
- `profile_loader.py` 不再维护本地硬编码引擎列表，改用统一 engine catalog。
- `data_reset_service.py` 的引擎 catalog 缓存路径改由 model lifecycle 提供。
- `config.py` 新增通用模型 catalog 配置键；旧 `OPENCODE_MODELS_*` 保留兼容映射（阶段一）。

### 6) agent_cli_manager 收口到 adapter profile
- `adapter_profile` 新增 `cli_management` 合同，集中声明：
  - `package`、`binary_candidates`
  - `credential_imports`、`credential_policy`
  - `resume_probe`
  - `layout`
- `agent_cli_manager` 不再维护 `ENGINE_PACKAGES`、`ENGINE_BINARY_CANDIDATES`、`CREDENTIAL_IMPORT_RULES`、`RESUME_HELP_HINTS` 常量。
- 布局初始化、凭据导入、凭据判定、resume 探测参数统一改为 profile 驱动。
- `engine_status_cache_service` 不再依赖 manager 内部引擎常量，改走统一 engine catalog。

## 兼容与迁移
- 阶段一（本 change）：引入通用键并保留旧键兼容映射。
- 阶段二（后续 change）：移除 `OPENCODE_MODELS_*` 旧键与引用。
