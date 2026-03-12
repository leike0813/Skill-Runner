# local-deploy-bootstrap Specification

## Purpose
定义本地一键部署脚本的依赖检查、路径初始化和运行时解析统一规则。
## Requirements
### Requirement: 系统 MUST 提供本地一键部署脚本
系统 MUST 提供 Linux/macOS 与 Windows 两套本地一键部署脚本，完成基础目录初始化与服务启动准备。系统同时 MUST 保持 `scripts/` 目录只包含正式支持的部署、启动、发布或受支持运维脚本；历史兼容、排障和实验脚本 MUST 迁出主目录。

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

### Requirement: release 安装器 MUST 执行固定版本下载与 SHA256 校验
系统 MUST 提供跨平台安装器脚本，并在执行前校验发布资产哈希。

#### Scenario: installer rejects corrupted artifact
- **WHEN** 下载资产哈希与发布校验值不一致
- **THEN** 安装器必须拒绝执行
- **AND** 返回明确的失败原因

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
