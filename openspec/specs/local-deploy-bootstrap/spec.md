# local-deploy-bootstrap Specification

## Purpose
定义本地一键部署脚本的依赖检查、路径初始化和运行时解析统一规则。
## Requirements
### Requirement: 系统 MUST 提供本地一键部署脚本
系统 MUST 保留 `deploy_local.sh/.ps1` 作为本地部署底层入口，但插件集成 SHOULD 调用稳定控制命令而非直接耦合脚本。

#### Scenario: Linux/macOS 一键部署
- **WHEN** 用户执行 `scripts/deploy_local.sh`
- **THEN** 脚本完成必要路径初始化与前置检查
- **AND** 输出明确的后续启动信息

#### Scenario: Windows 一键部署
- **WHEN** 用户执行 `scripts/deploy_local.ps1`
- **THEN** 脚本完成 Windows 本地路径初始化与前置检查
- **AND** 输出明确的后续启动信息

#### Scenario: local deploy binds loopback by default
- **WHEN** 用户执行本地部署脚本
- **THEN** 服务默认绑定 `127.0.0.1`
- **AND** 可通过环境变量显式覆盖 bind host

#### Scenario: optional ttyd dependency does not block core service startup
- **WHEN** 运行环境缺失 `ttyd`
- **THEN** 脚本输出可操作提示
- **AND** 核心 API 服务仍可启动
- 
#### Scenario: supported scripts remain in scripts directory
- **WHEN** 用户查看项目根目录 `scripts/`
- **THEN** 其中仅包含当前正式支持的部署/启动/运维入口
- **AND** 历史兼容或一次性脚本不再与正式入口混放

#### Scenario: deprecated or forensic scripts are relocated
- **WHEN** 用户需要访问历史兼容或排障脚本
- **THEN** 可以分别在 `deprecated/scripts/` 或 `artifacts/scripts/` 找到
- **AND** README 与容器化文档不会再把它们列为正式入口

### Requirement: 部署脚本 MUST 统一使用运行时解析规则
部署脚本 MUST 与服务端运行时解析逻辑一致，避免脚本初始化路径与服务实际读取路径不一致。

#### Scenario: 脚本初始化后服务可直接读取
- **WHEN** 一键部署脚本执行完成
- **THEN** 服务启动后读取同一组 data/cache/agent_home 路径
- **AND** 不出现模式错配导致的权限错误

### Requirement: 部署脚本 MUST 输出可诊断错误
部署脚本 MUST 在依赖缺失或权限不足时输出可执行的修复指引。

#### Scenario: 缺少 Node/npm
- **WHEN** 运行环境缺少 Node 或 npm
- **THEN** 脚本停止并输出安装指引
- **AND** 不进入半初始化状态

#### Scenario: optional ttyd dependency does not block API startup
- **WHEN** 运行环境缺失 `ttyd`
- **THEN** 脚本输出缺失告警与安装提示
- **AND** 核心 API 仍可继续启动

### Requirement: 系统 MUST 提供插件友好的运行控制命令
系统 MUST 提供稳定控制命令供插件调用，并覆盖 install/up/down/status/doctor。

#### Scenario: plugin uses stable local runtime control command
- **WHEN** 客户端调用 `skill-runnerctl up --mode local`
- **THEN** 系统启动本地服务并返回机器可读状态
- **AND** 后续可用 `status/down` 读取与控制生命周期

#### Scenario: skill-runnerctl local data dir defaults under local root
- **WHEN** 客户端通过 `skill-runnerctl` 在 local 模式启动服务且未显式设置 `SKILL_RUNNER_DATA_DIR`
- **THEN** 默认数据目录为 `<LocalRoot>/data`
- **AND** `<LocalRoot>` 在 Linux/macOS 下默认为 `$HOME/.local/share/skill-runner`，Windows 下默认为 `%LOCALAPPDATA%/SkillRunner`
- **AND** 若显式传入 `SKILL_RUNNER_DATA_DIR` 则继续以外部值为准

#### Scenario: service general default port is 9813
- **WHEN** 服务通过 `deploy_local.*` 或容器入口启动且未显式设置 `PORT`
- **THEN** 默认监听端口为 `9813`
- **AND** 显式设置 `PORT` 时必须优先使用外部值

#### Scenario: plugin local auto-deploy uses dedicated default port with fallback
- **WHEN** 客户端通过 `skill-runnerctl up --mode local` 启动且未显式设置 `--port`
- **THEN** 默认端口为 `29813`
- **AND** 当端口占用时可在 `29813-29823` 范围内自动回退到可用端口
- **AND** 显式传入 `--port` 或环境变量覆盖时仍以外部配置为准

#### Scenario: bootstrap/install default to managed subset
- **WHEN** 客户端调用 `skill-runnerctl bootstrap --json` 或 `skill-runnerctl install --json` 且未显式传入 `--engines`
- **THEN** 系统默认仅对 `opencode,codex` 执行 ensure
- **AND** 不再默认对全部受管 engine 做安装

#### Scenario: bootstrap/install supports explicit engine subset
- **WHEN** 客户端调用 `skill-runnerctl bootstrap --engines <csv|all|none> --json`
- **THEN** 系统按该目标集合执行 ensure
- **AND** `all` 保持全量 ensure
- **AND** `none` 仅执行布局初始化、状态刷新与报告落盘

### Requirement: 系统 MUST 提供可选清理策略的跨平台卸载脚本
系统 MUST 提供 Linux/macOS 与 Windows 两套卸载脚本，支持默认清理缓存/发布目录，并按选项清理 data 与 agent home。

#### Scenario: uninstall script performs stop-then-clean workflow
- **WHEN** 客户端调用 `skill-runner-uninstall.*`
- **THEN** 脚本先尝试执行 `skill-runnerctl down --mode local --json`
- **AND** 即使 down 失败，后续目录清理仍继续执行

#### Scenario: uninstall default cleanup scope
- **WHEN** 客户端调用卸载脚本且未启用额外清理选项
- **THEN** 脚本删除 `<LocalRoot>/releases`
- **AND** 删除 `<LocalRoot>/agent-cache/npm`、`<LocalRoot>/agent-cache/uv_cache`、`<LocalRoot>/agent-cache/uv_venv`
- **AND** 保留 `<LocalRoot>/data` 与 `<LocalRoot>/agent-cache/agent-home`

#### Scenario: uninstall supports optional data and agent-home cleanup
- **WHEN** 客户端调用卸载脚本并启用 `clear-data` 或 `clear-agent-home`
- **THEN** 脚本按选项额外删除 `<LocalRoot>/data` 与/或 `<LocalRoot>/agent-cache/agent-home`
- **AND** 当两个选项同时开启时，脚本在安全条件满足时尝试删除顶层 `<LocalRoot>`

#### Scenario: uninstall emits machine-readable summary with partial-success semantics
- **WHEN** 客户端以 JSON 模式调用卸载脚本（`--json` / `-Json`）
- **THEN** 输出包含 `ok`、`exit_code`、`message`、`local_root`
- **AND** 输出 `removed_paths`、`failed_paths`、`preserved_paths`、`options`、`down_result`
- **AND** 当存在清理失败时进程返回非零退出码，但保留已完成项结果

### Requirement: release 安装器 MUST 执行固定版本下载与 SHA256 校验
系统 MUST 提供跨平台安装器脚本，并在执行前校验发布资产哈希。

#### Scenario: installer rejects corrupted artifact
- **WHEN** 下载资产哈希与发布校验值不一致
- **THEN** 安装器必须拒绝执行
- **AND** 返回明确的失败原因

#### Scenario: installer emits machine-readable install output
- **WHEN** 用户以 JSON 模式执行 release 安装器（`skill-runner-install.sh --json` 或 `skill-runner-install.ps1 -Json`）
- **THEN** 安装器输出包含 `ok` 与 `install_dir` 的机器可读 JSON 结果
- **AND** 非 JSON 模式仍保留 `Installed to: <path>` 兼容文本输出

### Requirement: Release compose asset MUST be rendered from template without mutating repository compose
系统 MUST 从发布模板渲染 `docker-compose.release.yml` 作为 release 资产，且不得在发布流程中改写仓库内 `docker-compose.yml`。

#### Scenario: Tag release renders compose asset
- **WHEN** 仓库触发 `v*` tag 发布流程
- **THEN** CI 生成 `docker-compose.release.yml`
- **AND** 仓库内 `docker-compose.yml` 不被修改

#### Scenario: Release asset uses fixed image tag
- **WHEN** 生成 release compose 资产
- **THEN** `api` 服务使用发布 tag 对应镜像
- **AND** 可选 `e2e_client` 服务使用相同镜像 tag

### Requirement: Non-tag workflow MUST NOT publish release compose asset
系统 MUST 仅在 tag 发布时产出并上传 compose release 资产，避免非正式构建对外分发。

#### Scenario: Manual non-tag run
- **WHEN** 工作流以非 tag 方式触发
- **THEN** 不生成 `docker-compose.release.yml` release asset

### Requirement: Container bootstrap MUST expose actionable agent installation diagnostics
系统 MUST 在容器启动期间输出可操作的 agent 安装诊断信息，至少包含引擎名、返回码、耗时与失败摘要。

#### Scenario: Engine install failure emits structured diagnostics
- **WHEN** `agent_manager --ensure` 对某个 engine 安装失败
- **THEN** 启动日志包含该 engine 的结构化失败信息
- **AND** 信息包含 `engine`, `exit_code`, `duration_ms`, `stderr_summary`

### Requirement: Bootstrap diagnostics MUST be persisted under data dir
系统 MUST 将启动阶段诊断持久化到数据目录，便于离线排障。

#### Scenario: Bootstrap report is generated
- **WHEN** 容器完成启动流程
- **THEN** `${SKILL_RUNNER_DATA_DIR}/agent_bootstrap_report.json` 存在
- **AND** 报告包含每个 engine 的 ensure/install 结果

### Requirement: 部署示例 MUST 使用与系统 ttyd 解耦的高位默认端口
系统 MUST 在本地与容器部署示例中使用高位默认 ttyd 端口，避免与宿主机系统 `ttyd.service` 默认端口冲突。

#### Scenario: compose 默认端口
- **WHEN** 用户使用仓库默认 compose 文件部署
- **THEN** 内嵌 ttyd 映射端口默认为 `17681`
- **AND** 不占用 `7681`

#### Scenario: docker run 示例端口
- **WHEN** 用户参考 README 的 docker run 示例部署
- **THEN** ttyd 映射端口示例为 `17681:17681`
- **AND** 示例文案与 compose 配置一致

### Requirement: compose ttyd 映射 MUST 采用同号映射并提示不要拆分
系统 MUST 在 compose 中采用同号端口映射，并提示用户不要仅修改 host 或 container 端口的单侧值。

#### Scenario: compose 注释提示
- **WHEN** 用户查看 compose ttyd 端口配置
- **THEN** 文件包含“host/container 保持同号映射”的明确提示
- **AND** 默认配置为 `17681:17681`

### Requirement: Docker Compose 模板 MUST 采用主服务默认启用 + 客户端可选启用结构
系统 MUST 在容器部署模板中默认启用主服务，并提供可选的 E2E 客户端服务块，避免默认部署拓扑被客户端耦合。

#### Scenario: 默认 compose 启动只包含主服务
- **WHEN** 用户按默认 compose 文件执行启动（不改注释块）
- **THEN** 主服务被启动
- **AND** E2E 客户端服务不会被启动

#### Scenario: 用户按提示启用可选客户端
- **WHEN** 用户按 compose 文件中的提示取消 E2E 客户端服务注释
- **THEN** compose 可以额外启动客户端服务
- **AND** 不影响主服务既有启动参数

### Requirement: Compose 中可选客户端服务 MUST 与主服务复用同一镜像
系统 MUST 让 compose 的可选客户端服务与主服务服务复用同一镜像，仅通过入口命令或入口脚本区分运行角色。

#### Scenario: 单镜像双角色启动
- **WHEN** compose 同时启用主服务与可选客户端服务
- **THEN** 两个服务使用同一镜像标签
- **AND** 分别执行各自角色对应的启动命令

### Requirement: 系统 MUST 提供 bootstrap 控制命令并与 ensure 语义一致
系统 MUST 提供 `skill-runnerctl bootstrap`，并复用 `agent_manager --ensure` 的容错语义：单引擎安装失败可记为 `partial_failure`，但不阻断后续启动链路。

#### Scenario: bootstrap command follows ensure tolerance semantics
- **WHEN** 用户执行 `skill-runnerctl bootstrap --json`
- **THEN** 系统执行与 `agent_manager --ensure` 一致的引擎安装检查
- **AND** 单引擎安装失败时返回可继续结果并落盘诊断信息

#### Scenario: bootstrap diagnostics record requested and skipped engines
- **WHEN** 用户执行 `skill-runnerctl bootstrap --json`
- **THEN** 诊断报告包含 `summary.requested_engines`
- **AND** 包含 `summary.skipped_engines`
- **AND** 包含 `summary.resolved_mode`

### Requirement: release 安装器 MUST 自动执行 bootstrap 且失败仅告警
系统 MUST 在 release 安装器解压后自动执行一次 bootstrap；bootstrap 非零返回 MUST 仅告警，不阻断安装完成态。

#### Scenario: installer bootstrap failure is warning-only
- **WHEN** 安装器自动执行 bootstrap 且命令返回非零
- **THEN** 安装器输出明确 warning 与排障指引
- **AND** 安装流程保持完成态（不回滚已解压内容）

#### Scenario: installer bootstrap defaults to opencode and codex
- **WHEN** 安装器自动执行 bootstrap 且未显式覆盖 engine 集合
- **THEN** 默认仅 ensure `opencode,codex`
- **AND** 其余 engine 保持未安装态直到后续显式 bootstrap/install

### Requirement: 发布/本地部署链路 MUST 在 uv run 前注入 runtime profile 环境
系统在发布/本地部署链路中调用 `uv run` 前 MUST 注入 runtime profile 关键环境，包括 `UV_CACHE_DIR` 与 `UV_PROJECT_ENVIRONMENT`，避免解压目录生成漂移 `.venv`。

#### Scenario: wrapper injects uv cache and project environment
- **WHEN** 用户通过 `scripts/skill-runnerctl` 或 `scripts/skill-runnerctl.ps1` 触发运行控制命令
- **THEN** 包装脚本先注入 runtime profile 目录变量并创建目标目录
- **AND** 后续 `uv run` 使用注入后的缓存与环境目录

### Requirement: bootstrap/ensure MUST warm up opencode models after CLI is available
系统在 `agent_manager --ensure` 期间，当 OpenCode CLI 可用时 MUST 同步执行一次 `opencode models` 预热，以覆盖首装数据库初始化；该预热失败 MUST 仅告警并写入诊断，不阻断 ensure/bootstrap 主流程。

#### Scenario: opencode warmup succeeds after ensure
- **GIVEN** `opencode` CLI 已安装或可解析
- **WHEN** bootstrap/ensure 完成引擎安装检查
- **THEN** 系统执行一次 `opencode models` 预热并等待其自然结束
- **AND** 诊断报告包含 `opencode_warmup` 执行结果

#### Scenario: opencode warmup failure is warning-only
- **GIVEN** `opencode` 预热命令执行失败
- **WHEN** bootstrap/ensure 汇总结果
- **THEN** 系统记录 warning 与 `opencode_warmup` 失败信息
- **AND** 不改变 ensure/bootstrap 的“可继续启动”语义

### Requirement: README 部署文档 MUST 与实际默认部署行为保持一致
四语 README 中的 Docker 与本地部署说明 MUST 反映当前默认行为与依赖，避免用户按过时命令执行。

#### Scenario: direct docker run guidance uses current tag and mounts
- **WHEN** 用户参考 README 中“直接 docker run”命令
- **THEN** 镜像 tag 为 `latest`
- **AND** 命令包含与 compose 默认一致的挂载（`skills` 与 `skillrunner_cache`）

#### Scenario: local deployment and release compose are both documented
- **WHEN** 用户阅读 README 本地部署章节
- **THEN** 文档明确列出 `uv`、`node/npm` 与可选 `ttyd` 依赖
- **AND** 文档提供下载 release `docker-compose.release.yml` 并部署的方法（含可选 sha256 校验）

### Requirement: 系统 MUST 提供插件友好的宿主机控制入口
系统 MUST 提供稳定的宿主机控制命令用于插件调用，覆盖 install/up/down/status/doctor。

#### Scenario: plugin calls control CLI for local lifecycle
- **WHEN** 插件调用 `skill-runnerctl up --mode local`
- **THEN** 系统启动本地服务并返回机器可读状态
- **AND** 插件可通过 `status/down` 完成生命周期控制

### Requirement: 系统 MUST 提供 release 固定版本安装器并校验完整性
系统 MUST 提供跨平台安装器脚本并对下载资产执行 SHA256 校验。

#### Scenario: installer rejects checksum mismatch
- **WHEN** 下载资产哈希与发布校验值不一致
- **THEN** 安装器拒绝继续执行
- **AND** 返回明确错误信息

#### Scenario: tag release publishes installer source package assets
- **WHEN** CI 处理 `v*` tag 发布
- **THEN** Release 资产包含 `skill-runner-<version>.tar.gz` 与对应 `.sha256`
- **AND** 该源码包包含 `skills/*` 子模块内容

### Requirement: Windows command resolution MUST prefer executable wrappers over shim scripts
在 Windows 上，系统解析 engine CLI 与 ttyd 命令时 MUST 优先使用可执行包装器（`.cmd/.exe/.bat`），避免命中不可直接执行的无扩展 shim。

#### Scenario: managed engine command resolution on Windows
- **GIVEN** managed npm prefix 同时存在 `opencode` 与 `opencode.cmd`
- **WHEN** 系统解析 engine command
- **THEN** 结果 MUST 优先为 `opencode.cmd`（或其他可执行包装器）
- **AND** 不应优先返回无扩展 shim

#### Scenario: ttyd command resolution on Windows
- **GIVEN** PATH 中存在多个 ttyd 名称变体
- **WHEN** 系统解析 ttyd command
- **THEN** 解析顺序 MUST 优先 `.cmd/.exe/.bat`

### Requirement: Engine status probing MUST degrade gracefully on Windows process launch errors
在 Windows 上，命令探测与版本读取遇到 `OSError`（如 `WinError 193`）时，系统 MUST 退化为“该命令不可用/版本未知”，而不是中断启动流程。

#### Scenario: read_version hits WinError 193
- **GIVEN** 版本探测命令触发 `OSError`
- **WHEN** 系统执行 status 收集
- **THEN** `read_version` MUST 返回空值
- **AND** status 写入流程 MUST continue without uncaught exception

### Requirement: Windows concurrency probing MUST use parity resource sources
在 Windows 上，并发预算 MUST 使用平台等价资源探测，而不是静态 hard-cap fallback。

#### Scenario: Windows runtime computes concurrency budget from parity probes
- **GIVEN** runtime platform is Windows
- **WHEN** 系统计算并发上限
- **THEN** 内存维度 MUST 使用 `psutil.virtual_memory().available`
- **AND** fd 维度 MUST 使用 `_getmaxstdio`（`ucrtbase` 优先，`msvcrt` 备选）
- **AND** pid 维度 MUST 使用 Job Object `ActiveProcessLimit`
- **AND** 总上限 MUST 仍按 `min(cpu, mem, fd, pid, hard_cap)` 计算

#### Scenario: Windows runtime has no active-process job limit
- **GIVEN** runtime platform is Windows
- **AND** 当前进程不在受限 job 或 job 未设置 `ActiveProcessLimit`
- **WHEN** 系统计算 pid 维度
- **THEN** pid 维度 MUST NOT 额外收紧（按 `hard_cap` 参与最小值）

### Requirement: Windows parity probe dependency failures MUST fail fast
在 Windows 上，若并发等价探测依赖缺失或关键 API 不可用，系统 MUST fail-fast，禁止静默降级到固定 fallback。

#### Scenario: psutil missing on Windows
- **GIVEN** runtime platform is Windows
- **AND** `psutil` 不可用
- **WHEN** 服务初始化并发管理组件
- **THEN** 启动流程 MUST fail fast with actionable error
- **AND** 系统 MUST NOT silently fallback to fixed hard-cap concurrency

### Requirement: Qwen bootstrap configuration MUST be written to managed agent home

The bootstrap system SHALL write Qwen configuration to the managed agent home directory.

#### Scenario: Write Qwen bootstrap configuration

- **WHEN** the system bootstraps Qwen engine
- **THEN** it MUST create `agent_config/qwen/.qwen/` directory
- **AND** it MUST write `bootstrap.json` to `agent_config/qwen/.qwen/settings.json`

### Requirement: Qwen run-folder configuration MUST use the shared layering contract

Run-folder configuration SHALL be written to `run_dir/.qwen/settings.json` using the shared config-layering order.

#### Scenario: Compose Qwen run-folder settings

- **WHEN** a run is executed with Qwen engine
- **THEN** the system MUST create `run_dir/.qwen/` directory
- **AND** it MUST merge `engine_default -> skill defaults -> runtime overrides -> enforced`
- **AND** it MUST write the result to `run_dir/.qwen/settings.json`

### Requirement: Qwen skill injection MUST copy to run-local snapshot

Skills SHALL be copied to `run_dir/.qwen/skills/<skill_id>/`.

#### Scenario: Inject skill into Qwen run folder

- **WHEN** a run is materialized with a skill
- **THEN** the skill MUST be copied to `run_dir/.qwen/skills/<skill_id>/`
- **AND** the skill MUST include `SKILL.md` and declared assets

### Requirement: Workspace manager supports qwen workspace layout

The workspace manager SHALL support Qwen-specific workspace subdirectories.

#### Scenario: Create Qwen workspace subdirectories

- **WHEN** a run folder is created for Qwen engine
- **THEN** it MUST create `.qwen/`
- **AND** it MUST create `.qwen/skills/`

### Requirement: installer bootstrap defaults include qwen

Default managed bootstrap/ensure SHALL include `qwen` as a supported engine target.

#### Scenario: default ensure set contains qwen

- **WHEN** the system resolves its default managed bootstrap engines
- **THEN** `qwen` MUST be included in that default set

