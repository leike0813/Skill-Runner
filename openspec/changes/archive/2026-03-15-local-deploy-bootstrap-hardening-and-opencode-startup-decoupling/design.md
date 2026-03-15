## Context

本次变更目标是把“本地部署首次启动”路径从易阻塞、易漂移调整为可预测流程：

- Agent bootstrap 语义与 ensure 保持一致；
- OpenCode 首探测不阻塞 API 就绪；
- 本地 lease 对慢启动提供首次心跳容忍；
- 部署链路所有 `uv run` 调用前都具备 runtime profile 环境。

## Design Goals

1. bootstrap 与 ensure 使用同一容错语义（partial failure 可继续）。
2. API 启动路径不被模型探测阻塞。
3. 首次心跳窗口容忍慢机，不改变对外 lease API 结构。
4. 发布/本地部署脚本避免裸 `uv run` 触发解压目录 `.venv`。
5. README 四语部署文档与运行时默认行为保持一致，避免用户按过时命令部署。
6. 管理 UI 首页直接展示 ensure 缓存状态，减少用户跳转与排障成本。

## Design

### 1) Bootstrap/Ensure Unification

- `skill_runnerctl.py` 新增 `bootstrap` 子命令。
- `bootstrap` 与现有 `install` 共用同一内部逻辑：
  - 依赖检查（`uv/node/npm`）；
  - 调用 `uv run python scripts/agent_manager.py --ensure --bootstrap-report-file ...`；
  - 返回码完全继承 ensure。
- 发布安装器在解压后自动调用 `skill-runnerctl bootstrap --json`；
  - 若返回非零，仅输出 warning，不中断安装流程。
- `agent_manager --ensure` 完成后若检测到 OpenCode CLI，可追加一次同步 `opencode models` 预热：
  - 预热结果写入 bootstrap diagnostics（`opencode_warmup`）；
  - 失败仅 warning，不改变 ensure 主体语义。

### 2) OpenCode Startup Probe Decoupling

- `main.py` 启动期保留 `engine_model_catalog_lifecycle.start()`。
- `ENGINE_MODELS_CATALOG_STARTUP_PROBE=true` 时不再 `await refresh`，而是调用 `request_refresh_async(..., reason="startup")`。
- 若调度失败，仅 warning 并继续启动。

### 3) Unified Probe Timeout Policy

- `OpencodeModelCatalog` 启动探测与后续探测统一使用 `ENGINE_MODELS_CATALOG_PROBE_TIMEOUT_SEC`。
- 不再维护 cold-start 扩展超时配置与状态分支，减少分叉逻辑与配置负担。

### 4) First Heartbeat Grace

- `LocalRuntimeLeaseService` 在内存 lease 记录中增加首心跳状态。
- acquire 后若尚未收到首次 heartbeat，过期判定使用 `expires_at + grace`。
- 收到首次 heartbeat 后恢复常规 TTL 续租判定。
- 新增配置 `SKILL_RUNNER_LOCAL_RUNTIME_LEASE_FIRST_HEARTBEAT_GRACE_SEC`（默认 15）。

### 5) UV Runtime Profile Injection

- `scripts/skill-runnerctl(.ps1)` 包装脚本在调用 `uv run` 之前统一注入：
  - `SKILL_RUNNER_*` 关键目录变量；
  - `UV_CACHE_DIR`、`UV_PROJECT_ENVIRONMENT`；
  - 必要目录创建与 PATH 前置。
- `deploy_local.*` 继续按同一 profile 执行，并改为调用 `skill_runnerctl bootstrap`。

### 6) TTYD Missing: UI + API Gating

- `/ui/management/engines/table` 与 `/ui/engines` 统一注入 `ttyd_available`。
- `ttyd` 缺失时：
  - 引擎表格不渲染 `Start TUI` 按钮；
  - 内置终端交互主面板隐藏，仅保留不可用提示；
  - `POST /ui/engines/tui/session/start` 直接返回 `503`，避免运行时 `500`。

### 7) README Deployment Guidance Alignment (4 Languages)

- 四份 README 的直接 `docker run` 示例统一使用 `leike0813/skill-runner:latest`。
- 直接运行示例补充与 compose 默认一致的 volume：
  - `-v "$(pwd)/skills:/app/skills"`
  - `-v skillrunner_cache:/opt/cache`
- 增加“下载 release `docker-compose.release.yml` 并部署”的示例（含可选 `.sha256` 校验）。
- 本地章节统一改名为“本地部署 / Local Deployment / ローカルデプロイ / Déploiement local”，并明确依赖 `uv`、`node/npm` 与可选 `ttyd`。
- 所有 Inline/内嵌 TUI 说明补充 `ttyd` 依赖提示。

### 8) UI Home Engine Status Indicator

- `/ui` 首页在导航卡片与 Skill 安装卡片之间新增状态区块。
- 数据源使用 `engine_status_cache_service.get_snapshot()`，按 `keys.ENGINE_KEYS` 顺序展示。
- 状态映射统一为：
  - 绿色：`present=true` 且 `version` 非空
  - 黄色：`present=true` 且 `version` 为空
  - 红色：`present=false`
- 首页仅静态展示，不引入轮询刷新接口或定时器。

## Non-Goals

- 不新增 HTTP API 字段。
- 不改变 local lease acquire/heartbeat/release 请求/响应结构。
- 不扩展到仓库内所有历史脚本，仅覆盖发布/本地部署链路。
