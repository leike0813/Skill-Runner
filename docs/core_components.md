# 核心组件

本文档列出 Skill-Runner 各层核心模块、职责及关键接口。方法级 API 详情见 `docs/api_reference.md`。

---

## 1. Runtime 层（`server/runtime/`）

底层运行时基础设施，定义协议、状态机、适配器框架、鉴权编排与可观测性。

### 1.1 Session — 会话状态机

| 文件 | 职责 |
|------|------|
| `server/runtime/session/statechart.py` | **SSOT 实现**: 定义 `SessionEvent`、`Transition`、`TERMINAL_STATES`、`TRANSITIONS` 元组。所有状态/转移与 `server/contracts/invariants/session_fcmp_invariants.yaml` 一一对应。 |
| `server/runtime/session/timeout.py` | 会话超时策略（`interactive_reply_timeout_sec` 管理） |

### 1.2 Protocol — 协议层

| 文件 | 职责 |
|------|------|
| `server/runtime/protocol/event_protocol.py` | FCMP 单流事件协议实现：事件发射、cursor 管理、SSE 推送 |
| `server/runtime/protocol/factories.py` | 协议 payload 工厂：构建 `conversation.state.changed`、`assistant.message.*` 等标准 payload |
| `server/runtime/protocol/schema_registry.py` | 运行时 schema 注册：加载并缓存 `runtime_contract.schema.json`，提供写入端硬校验 |
| `server/runtime/protocol/parse_utils.py` | 协议解析工具 |

### 1.3 Adapter — 适配器框架

| 文件 | 职责 |
|------|------|
| `server/runtime/adapter/base_execution_adapter.py` | **统一适配器基类**: 定义 5 阶段生命周期（配置构建 → 环境准备 → Prompt 构建 → 执行 → 结果解析），各引擎适配器继承此基类 |
| `server/runtime/adapter/contracts.py` | 适配器合同接口定义 |
| `server/runtime/adapter/types.py` | 适配器类型定义（`EngineRunResult` 等） |
| `server/runtime/adapter/common/` | 引擎共享适配器工具 |

### 1.4 Auth — 鉴权编排

| 文件 | 职责 |
|------|------|
| `server/runtime/auth/session_lifecycle.py` | 鉴权会话生命周期管理 |
| `server/runtime/auth/session_store.py` | 鉴权会话存储 |
| `server/runtime/auth/driver_registry.py` | 鉴权驱动注册表 |
| `server/runtime/auth/callbacks.py` | OAuth 回调处理 |
| `server/runtime/auth/orchestrators/` | 鉴权编排器（各引擎鉴权流程） |

### 1.5 Observability — 可观测性

| 文件 | 职责 |
|------|------|
| `server/runtime/observability/run_observability.py` | FCMP/RASP 事件发射与记录 |
| `server/runtime/observability/run_read_facade.py` | 事件读取门面（history/range 查询） |
| `server/runtime/observability/run_source_adapter.py` | 事件源数据适配 |

---

## 2. Services 层（`server/services/`）

业务逻辑层，分为编排、平台能力、Skill 管理和 UI 服务四个子包。

### 2.1 Orchestration — 编排与执行

| 文件 | 职责 |
|------|------|
| `server/services/orchestration/job_orchestrator.py` | **编排门面**: 暴露稳定入口（run/cancel/recovery），委托生命周期服务执行主流程 |
| `server/services/orchestration/run_job_lifecycle_service.py` | run_job 生命周期主流程（preflight/execute/normalize/finalize） |
| `server/services/orchestration/run_bundle_service.py` | Run bundle 打包与 manifest 生成 |
| `server/services/orchestration/run_filesystem_snapshot_service.py` | 文件系统快照采集与差异计算 |
| `server/services/orchestration/run_audit_service.py` | 审计事件写入、done-marker 分类与 attempt 元数据落盘 |
| `server/services/orchestration/run_interaction_lifecycle_service.py` | 交互式会话生命周期（pending/reply/auto-decide） |
| `server/services/orchestration/run_recovery_service.py` | 启动恢复与重启对账 |
| `server/services/orchestration/orchestrator_ports.py` | 编排端口协议（`JobControlPort`） |
| `server/services/orchestration/run_store.py` | Run 持久化存储（文件系统 + 状态管理） |
| `server/services/orchestration/run_execution_core.py` | 执行核心逻辑 |
| `server/services/orchestration/run_interaction_service.py` | 交互服务（pending/reply 管理） |
| `server/services/orchestration/workspace_manager.py` | 工作区创建与管理 |

### 2.2 Engine Management — 引擎管理域

| 文件 | 职责 |
|------|------|
| `server/services/engine_management/engine_adapter_registry.py` | 引擎适配器注册与查找 |
| `server/services/engine_management/engine_auth_bootstrap.py` | 引擎鉴权引导 |
| `server/services/engine_management/engine_auth_flow_manager.py` | 鉴权流程管理 |
| `server/services/engine_management/model_registry.py` | 模型注册与查询 |
| `server/services/engine_management/agent_cli_manager.py` | Agent CLI 安装与版本管理 |
| `server/services/engine_management/engine_upgrade_manager.py` | 引擎升级管理 |
| `server/services/engine_management/engine_policy.py` | Skill 引擎策略计算与校验 |
| `server/services/engine_management/runtime_profile.py` | 运行时环境画像与子进程环境组装 |
| `server/services/engine_management/engine_command_profile.py` | 引擎命令 profile 合并 |
| `server/services/engine_management/engine_interaction_gate.py` | 交互会话门控 |
| `server/services/engine_management/engine_upgrade_store.py` | 升级任务持久化 |

### 2.3 Platform — 平台能力

| 文件 | 职责 |
|------|------|
| `server/services/platform/schema_validator.py` | JSON Schema 校验（输入/输出/meta-schema 预检） |
| `server/services/platform/concurrency_manager.py` | 并发槽管理（max_running_jobs） |
| `server/services/platform/cache_manager.py` | 缓存管理 |
| `server/services/platform/options_policy.py` | 运行时选项策略校验 |

### 2.4 Skill — Skill 管理

| 文件 | 职责 |
|------|------|
| `server/services/skill/skill_registry.py` | Skill 注册表：扫描 `skills/` 目录，加载 manifest，提供元数据查询 |
| `server/services/skill/skill_package_manager.py` | Skill 包管理（上传/安装/卸载） |
| `server/services/skill/skill_package_validator.py` | 包校验（meta-schema 预检） |
| `server/services/skill/skill_patcher.py` | Skill 运行时补丁（prompt 注入、输出约束） |
| `server/services/skill/skill_browser.py` | Skill 浏览服务 |
| `server/services/skill/temp_skill_run_manager.py` | 临时 Skill 运行管理 |

---

## 3. Engines 层（`server/engines/`）

每个引擎一个子包，包含 `adapter/`（适配器组件）和 `auth/`（鉴权组件）。

| 引擎 | 路径 | 适配器组件 | 鉴权组件 |
|------|------|-----------|---------|
| **Codex** | `server/engines/codex/` | `command_builder` / `config_composer` / `execution_adapter` / `stream_parser` / `trust_folder_strategy` | `oauth_proxy` / `runtime_handler` |
| **Gemini** | `server/engines/gemini/` | 同上结构 | 同上 + `cli_delegate` / `drivers/` |
| **iFlow** | `server/engines/iflow/` | 同上结构 | 同上 + `cli_delegate` / `drivers/` |
| **OpenCode** | `server/engines/opencode/` | 同上结构 | 双 OAuth proxy（Google/OpenAI）+ `provider_registry` |
| **Common** | `server/engines/common/` | 共享配置生成、Trust Registry | 共享 OAuth 逻辑、Callback Server 基类 |

---

## 4. Routers 层（`server/routers/`）

FastAPI 路由定义，按 API 域划分。

| 文件 | API 域 |
|------|--------|
| `management.py` | Management API（`/v1/management/*`）—— 推荐前端入口 |
| `jobs.py` | Jobs API（`/v1/jobs/*`）—— 执行链路 |
| `skills.py` | Skills API（`/v1/skills/*`） |
| `engines.py` | Engines API（`/v1/engines/*`） |
| `skill_packages.py` | Skill Packages API |
| `temp_skill_runs.py` | Temp Skill Runs API |
| `oauth_callback.py` | OAuth 回调路由 |
| `ui.py` | 内建 Web UI 路由 |

---

## 5. 全局配置

| 文件 | 职责 |
|------|------|
| `server/config.py` | Pydantic Settings 配置（环境变量 + YAML） |
| `server/core_config.py` | 核心常量 / 路径约定 |
| `server/models/` | 全局 Pydantic 模型包 + `server.models` facade 导出 |
| `server/logging_config.py` | 日志配置 |
| `server/main.py` | FastAPI 入口 |
