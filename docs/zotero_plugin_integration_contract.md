# Zotero Plugin Integration Contract

本文件定义 Zotero 插件与 Skill Runner 的最小稳定集成协议（后端仓库交付面）。

## 0) Zotero Bridge CLI 托管插件

- 后端运行时优先使用 `<SKILL_RUNNER_AGENT_CACHE_DIR>/plugin-bundles/zotero-bridge-cli-bundle` 中的受管 Zotero Bridge CLI bundle；内置 `plugins/zotero-bridge-cli-bundle` 作为 fallback。
- 服务启动后后台自动跟踪 `https://github.com/leike0813/zotero-agents` 的 `host-bridge/zotero-bridge-cli-bundle` 分支，校验通过后激活新 bundle。
- bundle 使用 `host-bridge.surface-release.v1` manifest：版本来自 `surface.version`，平台 CLI 与 SHA256 来自 `releaseSet.cli.binaries`，profile template 位于 `skills/zotero-bridge-cli/assets/profile.template.json`。
- 部署/bootstrap 会先将 manifest 规范化为统一 descriptor，再校验 wrapper skill、profile template、当前平台 CLI 及 SHA256；全部校验完成后才写入 managed agent home、profile 与 `SKILL_RUNNER_NPM_PREFIX/bin`。
- 本地部署沿用 `scripts/skill-runnerctl` 注入的 managed prefix PATH；Docker 部署沿用镜像内 `/opt/cache/skill-runner/npm/bin` PATH。
- agent subprocess 通过 `ZOTERO_BRIDGE_BIN` 获得 managed `zotero-bridge` 可执行文件的绝对路径。
- wrapper skill 从 bundle `skills/zotero-bridge-cli/` 同步到各 managed agent home 的全局 skill 目录，不作为 run-local skill 复制。
- managed profile 写入 `<SKILL_RUNNER_AGENT_CACHE_DIR>/zotero-bridge/bridge-profile.json`，agent subprocess 通过 `ZOTERO_BRIDGE_PROFILE` 定位。
- profile 不保存固定 endpoint 或 token；请求方通过 `runtime_options.env` 注入 `ZOTERO_BRIDGE_ENDPOINT`、`ZOTERO_BRIDGE_TOKEN`、`ZOTERO_BRIDGE_CONNECTION_MODE`。
- agent 使用 PATH 上的 `zotero-bridge` 命令访问 Zotero Bridge，不依赖 run-local shim。
- 不得打印、保存或回显 bearer token。
- Zotero bundle 无效时，bootstrap 会记录结构化插件失败并继续准备其他 engine；直接调用 bundle validator 或 installer 仍会返回失败。
- 外部 Zotero 插件无需显式触发 bundle 更新；`skill-runnerctl doctor --json`、`preflight --json` 和 `status --json` 会返回只读更新状态。管理员可在 System Console 查看当前版本与来源，并按“检查更新 → 安装更新”两阶段主动更新。

更多部署细节见 [Zotero Bridge CLI Managed Plugin](zotero_bridge_cli_managed_plugin.md)。

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
- 若未显式指定 engine 集合，默认仅预装 `opencode,codex`。
- `bootstrap` 非零时安装器仅告警，不回滚已解压内容；插件应读取诊断报告并给出可见提示。
- 安装器支持机器可读输出：
  - Linux/macOS: `scripts/skill-runner-install.sh --version <tag> --json`
  - Windows: `scripts/skill-runner-install.ps1 -Version <tag> -Json`
- JSON 成功输出至少包含：`ok`、`install_dir`、`version`、`bootstrap_exit_code`。
- 非 JSON 模式下安装器仍输出兼容文本行：`Installed to: <path>`。

## 2) 控制命令（插件唯一入口）

插件应通过 `skill-runnerctl` 调用，不直接耦合 `deploy_local.*`。

### Commands

- `bootstrap --json`
- `install --json`（兼容入口，当前语义与 `bootstrap` 一致）
- `preflight --json`
- `up --mode local|docker`
- `down --mode local|docker`
- `status --mode local|docker --json`
- `doctor --json`

### Local mode default

- 默认本地绑定：`127.0.0.1`
- 服务通用默认端口：`9813`（可覆盖）
- 插件本地自动部署默认端口：`29813`（可覆盖）
- 插件本地自动部署默认回退：`29813-29823`（共 11 个端口）
- `skill-runnerctl` 默认 LocalRoot：
  - Linux/macOS: `${SKILL_RUNNER_LOCAL_ROOT:-$HOME/.local/share/skill-runner}`
  - Windows: `${SKILL_RUNNER_LOCAL_ROOT:-%LOCALAPPDATA%\\SkillRunner}`
- `skill-runnerctl` 默认 `SKILL_RUNNER_DATA_DIR=<LocalRoot>/data`（可被显式环境变量覆盖）
- `skill-runnerctl` 默认 `SKILL_RUNNER_SKILLS_DIR=<LocalRoot>/skills`（可被显式环境变量覆盖）
- `skill-runnerctl` 默认 `SKILL_RUNNER_LOCAL_PORT=29813`、`SKILL_RUNNER_LOCAL_PORT_FALLBACK_SPAN=10`
- 依赖要求：`uv`、`node`、`npm`（`ttyd` 为可选，仅内嵌 TUI 需要）

### Wrapper 前置行为（shell/ps1）

- 推荐插件调用 `scripts/skill-runnerctl` 或 `scripts/skill-runnerctl.ps1`，不要直接调用 `scripts/skill_runnerctl.py`。
- wrapper 会设置默认环境：
  - `SKILL_RUNNER_RUNTIME_MODE=local`
  - `SKILL_RUNNER_LOCAL_PORT=29813`
  - `SKILL_RUNNER_LOCAL_PORT_FALLBACK_SPAN=10`
  - `SKILL_RUNNER_DATA_DIR=<LocalRoot>/data`
  - `SKILL_RUNNER_SKILLS_DIR=<LocalRoot>/skills`
  - `SKILL_RUNNER_AGENT_CACHE_DIR=<LocalRoot>/agent-cache`
  - `SKILL_RUNNER_AGENT_HOME=<LocalRoot>/agent-cache/agent-home`
- wrapper 会确保上述目录存在后再调用 `uv run python scripts/skill_runnerctl.py ...`。
- shell wrapper 缺少 `uv` 时直接退出 `exit=1` 并输出提示文本。
- PowerShell wrapper 缺少 `uv` 时抛错并返回非零。
- Windows 插件侧拉起 `skill-runnerctl.ps1` 时，必须使用“隐藏窗口”子进程参数（如 `CREATE_NO_WINDOW` 或等价 `windowStyle=hidden`），避免出现可见终端窗口。

### 输出与退出码通用规则

- 插件侧必须使用 `--json`，并只按 JSON 解析结果。
- 未使用 `--json` 时，仅输出 `message` 文本，不保证机器可读字段完整。
- `exit_code` 字段是协议真值；进程退出码与其一致。
- `argparse` 参数错误（未知命令/非法参数）会返回 `exit=2`，并输出 usage（非 JSON）。

### `install --json` / `bootstrap --json` 分支契约

公共说明：
- 二者语义一致，均执行 `agent_manager.py --ensure --bootstrap-report-file <data_dir>/agent_bootstrap_report.json`。
- 支持可选 `--engines <csv|all|none>`。
- 未显式传入 `--engines` 时，默认仅 ensure `opencode,codex`。
- 输出字段基线：
  - `ok`, `exit_code`, `mode`, `command`, `bootstrap_report_file`, `stdout`, `stderr`, `checks`, `message`
  - `requested_bootstrap_engines`

分支：

1. 依赖缺失（`uv/node/npm` 任一缺失）
- `ok=false`
- `exit_code=2`
- `message="Missing required dependencies."`
- `checks` 反映依赖布尔值

2. 启动 ensure 子进程失败（`Popen` 失败）
- `ok=false`
- `exit_code=127`
- `stderr` 含系统错误文本

3. ensure 返回 0
- `ok=true`
- `exit_code=0`
- `message` 为 `Install completed.` 或 `Bootstrap completed.`
- 注意：若报告文件中 `summary.outcome=partial_failure`，仍可能 `exit_code=0`（按策略允许继续）

4. ensure 返回非 0
- `ok=false`
- `exit_code=<ensure 返回码>`
- `message` 为 `Install failed.` 或 `Bootstrap failed.`

### `preflight --json` 分支契约

用途：
- 在不启动服务的前提下，做本地可启动性静态体检。
- 推荐插件在 `up` 前先执行，用于减少后续探测负担。

接口：
- `preflight --json [--host <host>] [--port <port>] [--port-fallback-span <span>]`

输出字段基线：
- `ok`, `exit_code`, `mode=local`, `message`
- `checks`（`dependencies` / `required_files` / `integrity` / `port` / `bootstrap_report` / `state_file`）
- `blocking_issues`（数组）
- `warnings`（数组）
- `suggested_next`（建议的 `up` 参数）

分级语义：
- `blocking_issues`：会导致 `exit_code!=0`，插件应中止自动启动并提示。
- `warnings`：仅提示，不阻断，`exit_code` 仍可能为 `0`。

blocking（非零）：
- 缺少依赖（`uv/node/npm`）
- 关键入口文件缺失或不可读
- 完整性清单缺失或不可解析（`integrity_manifest_*`）
- 完整性清单中的文件缺失（`integrity_file_missing`）
- 完整性清单中的文件哈希不一致（`integrity_hash_mismatch`）
- 端口参数非法
- 回退范围内无可用端口

warning（可继续）：
- bootstrap 报告缺失或不可解析
- bootstrap 报告 `summary.outcome=partial_failure`
- state 文件残留但 pid 不存活（stale）

退出码约定：
- `0`：无 blocking（可包含 warning）
- `1`：主要为端口可用性失败（如回退范围耗尽）
- `2`：参数/依赖/关键文件/完整性校验等硬失败

### `doctor --json` 分支契约

- `doctor` 当前固定返回：
  - `ok=true`
  - `exit_code=0`
- 输出字段：
  - `checks`: `uv/node/npm/docker/ttyd` 是否存在
  - `paths`: `data_dir/agent_cache_root/agent_home/npm_prefix/uv_cache_dir/uv_project_environment/state_file/local_log_file`
  - `env_snapshot`: `SKILL_RUNNER_RUNTIME_MODE/SKILL_RUNNER_LOCAL_BIND_HOST/SKILL_RUNNER_LOCAL_PORT/SKILL_RUNNER_LOCAL_PORT_FALLBACK_SPAN`
- 解释：
  - `doctor` 是环境诊断，不代表服务已启动，也不代表业务代码完整性已被验证。

### `status --mode local --json` 分支契约

输出字段基线：
- `ok=true`
- `exit_code=0`
- `mode=local`
- `status`：`running | starting | stopped`
- `pid`, `pid_alive`, `service_healthy`, `host`, `port`, `url`, `state_file`, `message`

状态含义：
- `running`: 健康探测 `GET /` 返回 `200`。
- `starting`: PID 存活但健康探测未通过。
- `stopped`: PID 不存活且健康探测未通过。

### `status --mode docker --json` 分支契约

1. 缺少 docker
- `ok=false`
- `exit_code=2`
- `message="docker is not installed."`

2. docker 可用
- 执行 `docker compose ps api --format json`
- 输出字段基线：
  - `ok`, `exit_code`, `mode=docker`, `status`, `detail`, `message`
- 若命令失败，额外包含 `stderr`
- `status` 由 `State/Status` 推断（包含 `running` 则视作运行中）

### `up --mode local --json` 分支契约

输出字段基线（成功或失败按分支扩展）：
- `ok`, `exit_code`, `mode`, `message`

分支：

1. 缺少 `uv`
- `ok=false`
- `exit_code=2`
- `message="uv is not installed."`

2. 已在运行（健康已通过）
- `ok=true`
- `exit_code=0`
- `message="Local runtime already running."`
- 返回 `host/port/url`

3. 端口参数非法（不在 1..65535）
- `ok=false`
- `exit_code=2`
- 返回 `requested_port`

4. 端口回退范围内无可用端口
- `ok=false`
- `exit_code=1`
- 返回 `host/requested_port/port_fallback_span/tried_ports`

5. 拉起进程失败（拿不到有效 pid）
- `ok=false`
- `exit_code=1`
- `message="Failed to start local runtime."`

6. 拉起后健康检查超时或进程提前退出
- `ok=false`
- `exit_code=1`
- 返回 `pid/log_path/host/requested_port/port/port_fallback_span/port_fallback_used/tried_ports`

7. 启动成功
- `ok=true`
- `exit_code=0`
- 返回 `pid/host/requested_port/port/port_fallback_span/port_fallback_used/tried_ports/url/log_path`
- 若发生回退，`message` 会明确提示 `fallback port`

### `up --mode docker --json` 分支契约

1. 缺少 docker
- `ok=false`
- `exit_code=2`
- `message="docker is not installed."`

2. 执行 `docker compose up -d api`
- `ok=(returncode==0)`
- `exit_code=<docker returncode>`
- 字段：`mode=docker/message/stdout/stderr`

### `down --mode local --json` 分支契约

- 始终返回成功（幂等）：
  - `ok=true`
  - `exit_code=0`
  - `mode=local`
  - `message="Local runtime stopped."`
- 行为：尝试终止 state 记录的 pid，并删除 state 文件。

### `down --mode docker --json` 分支契约

1. 缺少 docker
- `ok=false`
- `exit_code=2`
- `message="docker is not installed."`

2. 执行 `docker compose stop api`
- `ok=(returncode==0)`
- `exit_code=<docker returncode>`
- 字段：`mode=docker/message/stdout/stderr`

## 3) Bootstrap/Ensure 语义

- `bootstrap/install` 内部执行 `agent_manager.py --ensure`，行为与 ensure 保持一致。
- 默认 target set 为 `opencode,codex`；其他 engine 需显式再次执行 `bootstrap/install --engines <engine>`。
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

1. 安装 Release（推荐机器可读）：`skill-runner-install.* --version <tag> --json`（PowerShell 使用 `-Json`）
2. 读取 `${SKILL_RUNNER_DATA_DIR}/agent_bootstrap_report.json`（若 `summary.outcome=partial_failure`，前台提示但允许继续）
3. `skill-runnerctl preflight --json`（`exit_code!=0` 则中止自动启动并展示 blocking）
4. `skill-runnerctl up --mode local --json`
5. `POST /v1/local-runtime/lease/acquire`（使用 `up` 返回的实际 `host/port/url`，不要硬编码端口）
6. `POST /v1/system/handshake` 查询协议能力；旧后端没有该接口时，插件可按 legacy 逻辑仅视为支持 `skillrunner.job.v1`
7. 按 `heartbeat_interval_seconds` 定时 `heartbeat`
8. 插件退出时 `release`
9. 可选 `skill-runnerctl down --mode local --json`

## 6) Handshake capability contract

插件在提交任务前可调用：

`POST /v1/system/handshake`

请求：
```json
{
  "schema": "zotero-agents.skillrunner-handshake.request.v1",
  "client": {
    "name": "zotero-agents",
    "version": "0.5.4"
  },
  "requested_protocols": [
    "skillrunner.job.v1",
    "skillrunner.sequence.v1"
  ]
}
```

响应：
```json
{
  "schema": "zotero-agents.skillrunner-handshake.response.v1",
  "backend": {
    "name": "Skill-Runner",
    "version": "0.7.2"
  },
  "protocols": {
    "skillrunner.job.v1": { "supported": true },
    "skillrunner.sequence.v1": { "supported": false }
  }
}
```

约束：
- `POST /v1/system/handshake` 是协议能力查询入口。
- `GET|HEAD /v1/system/ping` 仅表示后端可达，不表示协议能力。
- `skillrunner.job.v1` 是第一版支持的任务提交协议。
- 当前后端不原生支持整段 sequence workflow 执行，因此 `skillrunner.sequence.v1.supported=false`。
- 未知协议不得导致 500，可返回 `supported=false`。
- 协议 ID 是稳定契约；后续新增语义必须新增 ID，不能复用旧 ID 改行为。

## 7) 卸载契约（跨平台）

推荐脚本：

- Linux/macOS: `scripts/skill-runner-uninstall.sh`
- Windows: `scripts/skill-runner-uninstall.ps1`

参数：

- 清理 data：`--clear-data` / `-ClearData`
- 清理 agent home：`--clear-agent-home` / `-ClearAgentHome`
- JSON 输出：`--json` / `-Json`
- 覆盖本地根目录：`--local-root <path>` / `-LocalRoot <path>`

默认清理范围（未加可选开关时）：

- `<LocalRoot>/releases`
- `<LocalRoot>/agent-cache/npm`
- `<LocalRoot>/agent-cache/uv_cache`
- `<LocalRoot>/agent-cache/uv_venv`

附加行为：

- 卸载开始前会先尝试执行 `skill-runnerctl down --mode local --json`。
- 即使 `down` 失败，卸载仍继续，并在结果中返回 `down_result`。
- 当 `clear-data` 与 `clear-agent-home` 同时开启时，脚本会尝试删除顶层 `LocalRoot`（带安全护栏）。

JSON 输出字段：

- `ok`, `exit_code`, `message`
- `local_root`
- `removed_paths`, `failed_paths`, `preserved_paths`
- `options.clear_data`, `options.clear_agent_home`
- `down_result.invoked`, `down_result.ok`, `down_result.exit_code`, `down_result.stdout`, `down_result.stderr`

退出语义：

- 全部成功：`exit_code=0`
- 部分失败：保留已完成清理结果，同时 `exit_code!=0`

## 8) Version management

后端版本以 `pyproject.toml` 的 `[project].version` 为单一事实源。发布前使用统一脚本更新版本：

```bash
uv run --project="$HOME/.ar" --locked -- python scripts/bump_version.py 0.7.3
```

创建 tag 后，发布流程会校验 tag 与项目版本一致：

```bash
uv run --project="$HOME/.ar" --locked -- python scripts/bump_version.py --check-tag v0.7.3
```

脚本只更新或校验 `pyproject.toml`，不创建 tag、不提交代码、不切换分支。

## 9) Error handling

- `local-runtime` 接口返回 `409`：说明当前不是 local 模式，插件应停止 lease 流程。
- `heartbeat` 返回 `404`：lease 已失效，插件应重新 `acquire`。
- `preflight` 返回非零：插件应中止自动启动并展示 `blocking_issues`。
- `preflight` 若为完整性相关失败：插件应提示用户重装同版本 release 包，不应直接继续 `up`。
- `up` 返回非零：插件应执行 `status + doctor` 作为诊断回退，并记录结果用于排查。
- `bootstrap/install` 返回非零：视为硬失败（依赖缺失或启动前置失败），插件应中止自动启动并提示用户修复环境。
- `bootstrap/install` 返回零但报告为 `partial_failure`：插件可继续 `up`，同时展示“部分引擎未就绪”警告与报告摘要。
- 插件若后续需要其他未预装 engine，应先显式调用 `skill-runnerctl bootstrap --engines <engine> --json`。
