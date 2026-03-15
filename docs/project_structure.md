# Project Structure

本文档描述 Skill-Runner 的代码目录结构。

## 根目录

```
Skill-Runner/
├── server/                 # FastAPI 服务主包
├── skills_builtin/         # 内建 Skill 包（随仓库发布）
├── skills/                 # 用户 Skill 包（运行时安装/覆盖）
├── tests/                  # 测试套件
├── agent_harness/          # 外部运行时 harness
├── e2e_client/             # 内建 E2E 示例客户端
├── scripts/                # 工具脚本
├── docs/                   # 项目文档
├── openspec/               # OpenSpec 规范与变更
├── data/                   # 运行时数据（runs/日志/缓存，gitignored）
├── pyproject.toml          # 依赖与构建配置
├── Dockerfile              # 容器化
├── docker-compose.yml      # 容器编排
└── AGENTS.md               # SSOT 导航表
```

## server/ 主包

```
server/
├── main.py                 # FastAPI 入口 + Uvicorn 启动
├── config.py               # Pydantic Settings 配置
├── core_config.py          # 核心常量 / 路径约定
├── models/                 # 全局 Pydantic 模型包（领域拆分 + facade 导出）
├── logging_config.py       # 日志配置
│
├── engines/                # 引擎适配层（每引擎一子包）
│   ├── common/             # 引擎共享组件
│   │   ├── callbacks/      #   OAuth callback server 基类
│   │   ├── config/         #   配置生成工具
│   │   ├── openai_auth/    #   OpenAI 系 OAuth 通用逻辑
│   │   └── trust_registry.py
│   ├── codex/              # Codex CLI 引擎
│   │   ├── adapter/        #   适配器（command_builder / config_composer / execution_adapter / stream_parser）
│   │   └── auth/           #   鉴权（oauth_proxy / runtime_handler）
│   ├── gemini/             # Gemini CLI 引擎
│   │   ├── adapter/        #   适配器
│   │   └── auth/           #   鉴权（含 cli_delegate / drivers）
│   ├── iflow/              # iFlow CLI 引擎
│   │   ├── adapter/        #   适配器
│   │   └── auth/           #   鉴权
│   └── opencode/           # OpenCode 引擎
│       ├── adapter/        #   适配器
│       ├── auth/           #   鉴权（含 Google/OpenAI 双 OAuth proxy）
│       └── models/         #   模型列表
│
├── runtime/                # 运行时核心层
│   ├── adapter/            # 统一适配器框架
│   │   ├── base_execution_adapter.py  # 适配器基类（5 阶段生命周期）
│   │   ├── contracts.py    #   适配器合同接口
│   │   ├── types.py        #   类型定义
│   │   └── common/         #   引擎共享适配器工具
│   ├── auth/               # 运行时鉴权编排
│   │   ├── session_lifecycle.py  # 会话鉴权生命周期
│   │   ├── session_store.py     # 会话存储
│   │   ├── driver_registry.py   # 鉴权驱动注册
│   │   ├── callbacks.py         # 鉴权回调
│   │   ├── log_writer.py        # 鉴权日志
│   │   └── orchestrators/       # 鉴权编排器
│   ├── execution/          # 执行策略（预留扩展）
│   ├── observability/      # 可观测性
│   │   ├── run_observability.py    # FCMP/RASP 事件发射
│   │   ├── run_read_facade.py      # 事件读取门面
│   │   ├── run_source_adapter.py   # 事件源适配
│   │   └── contracts.py            # 可观测性合同
│   ├── protocol/           # 协议层
│   │   ├── event_protocol.py    # FCMP 事件协议实现
│   │   ├── factories.py         # 协议 payload 工厂
│   │   ├── schema_registry.py   # 运行时 schema 注册
│   │   ├── parse_utils.py       # 协议解析工具
│   │   └── contracts.py         # 协议合同
│   └── session/            # 会话状态机
│       ├── statechart.py   # Canonical Statechart（SSOT 实现锚点）
│       └── timeout.py      # 会话超时策略
│
├── services/               # 业务服务层
│   ├── orchestration/      # 编排与执行
│   │   ├── job_orchestrator.py         # 作业编排门面（稳定入口）
│   │   ├── run_job_lifecycle_service.py # run_job 生命周期主流程服务
│   │   ├── run_bundle_service.py       # bundle 打包服务
│   │   ├── run_filesystem_snapshot_service.py # 文件快照与差异服务
│   │   ├── run_audit_service.py        # 审计与完成分类服务
│   │   ├── run_audit_contract_service.py # 审计合同与骨架初始化
│   │   ├── run_auth_orchestration_service.py # 鉴权编排服务
│   │   ├── run_interaction_lifecycle_service.py # 交互生命周期服务
│   │   ├── run_interaction_service.py  # 交互服务（reply/pending）
│   │   ├── run_recovery_service.py     # 启动恢复与对账服务
│   │   ├── run_store.py                # Run 持久化存储
│   │   ├── run_state_service.py        # Run 状态写入服务
│   │   ├── run_execution_core.py       # 执行核心
│   │   ├── run_projection_service.py   # 投影服务
│   │   ├── run_service_log_mirror.py   # 服务日志镜像
│   │   ├── run_skill_materialization_service.py # Skill 物化服务
│   │   ├── workspace_manager.py        # 工作区管理
│   │   ├── run_cleanup_manager.py      # 清理管理
│   │   ├── run_folder_trust_manager.py # 信任文件夹管理
│   │   ├── manifest_artifact_inference.py # Manifest 产物推断
│   │   ├── runtime_observability_ports.py # 可观测性端口
│   │   └── runtime_protocol_ports.py   # 协议端口
│   ├── engine_management/   # 引擎管理域
│   │   ├── agent_cli_manager.py        # Agent CLI 管理
│   │   ├── engine_adapter_registry.py  # 引擎适配器注册
│   │   ├── engine_auth_bootstrap.py    # 引擎鉴权引导
│   │   ├── engine_auth_flow_manager.py # 鉴权流程管理
│   │   ├── engine_auth_strategy_service.py # 鉴权策略服务
│   │   ├── engine_catalog.py           # 引擎目录
│   │   ├── engine_command_profile.py   # 引擎命令配置
│   │   ├── engine_interaction_gate.py  # 引擎交互门控
│   │   ├── engine_model_catalog_lifecycle.py # 模型目录生命周期
│   │   ├── engine_policy.py            # 引擎策略
│   │   ├── engine_status_cache_service.py # 引擎状态缓存
│   │   ├── engine_upgrade_manager.py   # 引擎升级管理
│   │   ├── engine_upgrade_store.py     # 升级状态存储
│   │   ├── model_registry.py           # 模型注册
│   │   └── runtime_profile.py          # 运行时配置文件
│   ├── platform/           # 平台能力
│   │   ├── schema_validator.py    # JSON Schema 校验
│   │   ├── concurrency_manager.py # 并发管理
│   │   ├── cache_manager.py       # 缓存管理
│   │   ├── cache_key_builder.py   # 缓存键构建
│   │   ├── data_reset_service.py  # 数据重置服务
│   │   ├── options_policy.py      # 运行时选项策略
│   │   ├── process_supervisor.py  # 子进程监管
│   │   ├── process_termination.py # 子进程终止
│   │   ├── process_lease_store.py # 进程租约存储
│   │   ├── run_file_filter_service.py # 文件过滤服务
│   │   ├── system_settings_service.py # 系统设置服务
│   │   ├── aiosqlite_compat.py    # SQLite 异步兼容层
│   │   └── async_compat.py        # 异步兼容工具
│   ├── skill/              # Skill 管理
│   │   ├── skill_registry.py           # Skill 注册表
│   │   ├── skill_package_manager.py    # 包管理
│   │   ├── skill_package_validator.py  # 包校验
│   │   ├── skill_patcher.py            # Skill 运行时补丁
│   │   ├── skill_patch_output_schema.py # 输出 Schema 补丁
│   │   ├── skill_patch_templates.py    # 补丁模板
│   │   ├── skill_browser.py            # Skill 浏览
│   │   ├── skill_install_store.py      # 安装状态存储
│   │   ├── temp_skill_run_manager.py   # 临时 Skill 运行管理
│   │   ├── temp_skill_run_store.py     # 临时运行存储
│   │   └── temp_skill_cleanup_manager.py # 清理管理
│   └── ui/                 # UI 服务
│       ├── engine_shell_capability_provider.py # 引擎 Shell 能力提供
│       ├── ui_auth.py             # UI 鉴权服务
│       └── ui_shell_manager.py    # UI Shell 管理
│
├── routers/                # API 路由层
│   ├── management.py       # Management API（/v1/management/*）
│   ├── jobs.py             # Jobs API（/v1/jobs/*）
│   ├── skills.py           # Skills API（/v1/skills/*）
│   ├── engines.py          # Engines API（/v1/engines/*）
│   ├── skill_packages.py   # Skill Packages API
│   ├── temp_skill_runs.py  # Temp Skill Runs API
│   ├── oauth_callback.py   # OAuth 回调
│   └── ui.py               # 内建 UI 路由
│
├── config_registry/        # 引擎配置注册表
│   ├── keys.py            # 引擎标识常量（ENGINE_KEYS）
│   ├── loaders.py         # 配置加载器
│   └── registry.py        # 配置注册表
│
├── contracts/              # 协议合同与 Schema
│   ├── schemas/           # JSON Schema（runtime_contract 等）
│   └── invariants/        # 不变量合同（session_fcmp_invariants 等）
│
└── assets/                 # 静态资源
    └── templates/          # Jinja2 模板
        ├── gemini_default.j2    # Gemini prompt 模板
        ├── codex_default.j2     # Codex prompt 模板
        ├── iflow_default.j2     # iFlow prompt 模板
        └── ui/                  # Web UI HTML 模板
```

> **注意**: 引擎配置（`default.json`/`enforced.json`）和模型列表已迁移至 `server/engines/<engine>/config/` 和 `server/engines/<engine>/models/`。

## 其他顶层目录

| 目录 | 说明 |
|------|------|
| `skills_builtin/` | 内建 Skill 包（每个 skill 一个子目录，含 `SKILL.md` + `assets/runner.json`） |
| `skills/` | 用户 Skill 包（运行时安装目录；同 `skill_id` 时覆盖内建） |
| `tests/` | 测试套件（`unit/`、`integration/`、`common/`、`e2e/`、`suites/`） |
| `agent_harness/` | 外部运行时 harness（独立 CLI 测试环境） |
| `e2e_client/` | 内建 E2E 示例客户端（端口 9814） |
| `scripts/` | 工具脚本（启动、清理、部署等） |
| `docs/` | 项目文档（API 参考、协议规范、合同定义） |
| `openspec/` | OpenSpec 规范（`specs/`）与变更（`changes/`） |
| `data/` | 运行时数据（`runs/`、`logs/`、`requests/`，gitignored） |
