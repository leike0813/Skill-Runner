## Why

本地部署在首次启动链路存在三个脆弱点：

1. Agent ensure 安装与服务启动强耦合，首次安装阶段容易让启动体验不稳定。
2. OpenCode 模型探测在启动期等待执行，慢机或首装场景会放大阻塞。
3. 本地租约首次心跳与启动耗时没有容忍窗口，可能造成误判过期。
4. 发布/本地部署脚本仍存在裸 `uv run` 入口，可能在解压目录意外创建 `.venv`。
5. README 四语中的 Docker 与本地部署指引存在口径漂移（镜像 tag、挂载、release compose 下载方式、依赖提示）。
6. 管理 UI 首页缺少引擎可用性指示，用户需要跳转到引擎页才能确认 ensure 结果。

需要通过同一个 change 收敛 bootstrap 策略、启动时序与部署环境注入规则。

## What Changes

- 新增 `skill-runnerctl bootstrap`，内部复用 `agent_manager --ensure`，并保持“部分失败仅告警记录、可继续启动”策略。
- 发布安装器在解压后自动执行 bootstrap；bootstrap 非零仅告警，不阻断安装完成态。
- `bootstrap/ensure` 在 OpenCode 可用后执行一次同步 `opencode models` 预热（失败仅告警，不阻断链路）。
- 服务启动阶段不再 `await` OpenCode 模型探测，改为后台异步触发首次 refresh。
- OpenCode 启动与后续探测统一使用 `ENGINE_MODELS_CATALOG_PROBE_TIMEOUT_SEC` 超时口径。
- 本地租约新增“首次心跳宽限”（默认 15s，环境变量可覆盖），首次过期判定包含宽限。
- `ttyd` 缺失时前后端统一禁用内置 Shell/TUI：UI 隐藏入口、启动接口直接返回 `503`。
- 发布/本地部署链路统一注入 runtime profile 关键环境（含 `UV_CACHE_DIR`、`UV_PROJECT_ENVIRONMENT`），避免裸 `uv run` 造成目录漂移。
- README（中/英/日/法）统一 Docker 与本地部署说明：`docker run` 使用 `latest` + compose 等价挂载 + release compose 下载部署方法 + 本地依赖/ttyd 提示。
- 管理 UI 首页新增引擎状态指示器：基于 ensure 缓存快照静态展示绿/黄/红状态，无自动轮询刷新。

## Capabilities

### Modified Capabilities

- `local-deploy-bootstrap`
- `opencode-model-catalog-refresh`
- `interactive-job-api`
- `ui-engine-management`

## Impact

- Affected code:
  - `scripts/skill_runnerctl.py`
  - `scripts/skill-runnerctl`
  - `scripts/skill-runnerctl.ps1`
  - `scripts/skill-runner-install.sh`
  - `scripts/skill-runner-install.ps1`
  - `scripts/deploy_local.sh`
  - `scripts/deploy_local.ps1`
  - `server/main.py`
  - `server/config.py`
  - `server/engines/opencode/models/catalog_service.py`
  - `server/routers/ui.py`
  - `server/assets/templates/ui/index.html`
  - `server/assets/templates/ui/base.html`
  - `server/locales/{zh,en,ja,fr}.json`
  - `README.md`
  - `README_CN.md`
  - `README_JA.md`
  - `README_FR.md`
  - `server/assets/templates/ui/engines.html`
  - `server/assets/templates/ui/partials/engines_table.html`
  - `server/services/platform/local_runtime_lease_service.py`
  - `tests/unit/*` (相关新增/更新)
- API impact: 无破坏式变更。
- Protocol impact: 无字段级变更。
