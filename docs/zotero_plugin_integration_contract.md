# Zotero Plugin Integration Contract

本文件定义 Zotero 插件与 Skill Runner 的最小稳定集成协议（后端仓库交付面）。

## 1) 安装与版本来源

- 插件应下载 **GitHub Release 固定版本**资产，不使用主分支快照。
- 安装前必须校验 SHA256；校验失败必须拒绝执行。
- 推荐使用：
  - `scripts/skill-runner-install.sh`
  - `scripts/skill-runner-install.ps1`
- 安装器依赖同版本 Release 资产：
  - `skill-runner-<version>.tar.gz`
  - `skill-runner-<version>.tar.gz.sha256`
- 安装器在解压后会自动执行一次 `skill-runnerctl bootstrap --json`。
- `bootstrap` 非零时安装器仅告警，不回滚已解压内容；插件应读取诊断报告并给出可见提示。

## 2) 控制命令（插件唯一入口）

插件应通过 `skill-runnerctl` 调用，不直接耦合 `deploy_local.*`。

### Commands

- `bootstrap --json`
- `install --json`（兼容入口，当前语义与 `bootstrap` 一致）
- `up --mode local|docker`
- `down --mode local|docker`
- `status --mode local|docker --json`
- `doctor --json`

### Local mode default

- 默认本地绑定：`127.0.0.1`
- 默认端口：`8000`（可覆盖）
- 依赖要求：`uv`、`node`、`npm`（`ttyd` 为可选，仅内嵌 TUI 需要）

## 3) Bootstrap/Ensure 语义

- `bootstrap/install` 内部执行 `agent_manager.py --ensure`，行为与 ensure 保持一致。
- 引擎级失败会写入诊断报告 `summary.outcome=partial_failure`，但整体进程可返回成功并继续启动链路。
- `bootstrap/install` 阶段会在 OpenCode CLI 可用时执行一次 `opencode models` 预热（失败仅告警，不阻断后续 `up`）。
- 诊断报告默认路径：`${SKILL_RUNNER_DATA_DIR}/agent_bootstrap_report.json`。

## 4) Local lease lifecycle

仅在 `SKILL_RUNNER_RUNTIME_MODE=local` 下使用：

- `POST /v1/local-runtime/lease/acquire`
- `POST /v1/local-runtime/lease/heartbeat`
- `POST /v1/local-runtime/lease/release`

建议心跳周期：优先使用 `acquire` 返回的 `heartbeat_interval_seconds`。  
默认 TTL：`60s`。  
默认首次心跳宽限：`15s`（`SKILL_RUNNER_LOCAL_RUNTIME_LEASE_FIRST_HEARTBEAT_GRACE_SEC`）。

行为约束：

- 正常退出：插件先 `release`（可选再 `down`）。
- 异常退出：若未 release/down，服务在租约过期后可自停（首次心跳前包含宽限窗口）。
- 多租约场景：存在任一有效租约即保活；全部失效后进入自停路径。

## 5) Recommended sequence

1. 安装 Release：`skill-runner-install.* --version <tag>`
2. 读取 `${SKILL_RUNNER_DATA_DIR}/agent_bootstrap_report.json`（若 `summary.outcome=partial_failure`，前台提示但允许继续）
3. `skill-runnerctl up --mode local --json`
4. `POST /v1/local-runtime/lease/acquire`
5. 按 `heartbeat_interval_seconds` 定时 `heartbeat`
6. 插件退出时 `release`
7. 可选 `skill-runnerctl down --mode local --json`

## 6) Error handling

- `local-runtime` 接口返回 `409`：说明当前不是 local 模式，插件应停止 lease 流程。
- `heartbeat` 返回 `404`：lease 已失效，插件应重新 `acquire`。
- `status` 返回非 running：插件可重试 `up`，并记录 `doctor` 结果用于诊断。
- `bootstrap/install` 返回非零：视为硬失败（依赖缺失或启动前置失败），插件应中止自动启动并提示用户修复环境。
- `bootstrap/install` 返回零但报告为 `partial_failure`：插件可继续 `up`，同时展示“部分引擎未就绪”警告与报告摘要。
