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

## 2) 控制命令（插件唯一入口）

插件应通过 `skill-runnerctl` 调用，不直接耦合 `deploy_local.*`。

### Commands

- `install`
- `up --mode local|docker`
- `down --mode local|docker`
- `status --mode local|docker --json`
- `doctor --json`

### Local mode default

- 默认本地绑定：`127.0.0.1`
- 默认端口：`8000`（可覆盖）

## 3) Local lease lifecycle

仅在 `SKILL_RUNNER_RUNTIME_MODE=local` 下使用：

- `POST /v1/local-runtime/lease/acquire`
- `POST /v1/local-runtime/lease/heartbeat`
- `POST /v1/local-runtime/lease/release`

建议心跳周期：`20s`。  
默认 TTL：`60s`。

行为约束：

- 正常退出：插件先 `release`（可选再 `down`）。
- 异常退出：若未 release/down，服务在 TTL 超时后可自停。
- 多租约场景：存在任一有效租约即保活；全部失效后进入自停路径。

## 4) Recommended sequence

1. `skill-runnerctl install --json`
2. `skill-runnerctl up --mode local --json`
3. `POST /v1/local-runtime/lease/acquire`
4. 定时 `heartbeat`
5. 插件退出时 `release`
6. 可选 `skill-runnerctl down --mode local --json`

## 5) Error handling

- `local-runtime` 接口返回 `409`：说明当前不是 local 模式，插件应停止 lease 流程。
- `heartbeat` 返回 `404`：lease 已失效，插件应重新 `acquire`。
- `status` 返回非 running：插件可重试 `up`，并记录 `doctor` 结果用于诊断。
