## ADDED Requirements

### Requirement: 系统 MUST 提供 bootstrap 控制命令并与 ensure 语义一致
系统 MUST 提供 `skill-runnerctl bootstrap`，并复用 `agent_manager --ensure` 的容错语义：单引擎安装失败可记为 `partial_failure`，但不阻断后续启动链路。

#### Scenario: bootstrap command follows ensure tolerance semantics
- **WHEN** 用户执行 `skill-runnerctl bootstrap --json`
- **THEN** 系统执行与 `agent_manager --ensure` 一致的引擎安装检查
- **AND** 单引擎安装失败时返回可继续结果并落盘诊断信息

### Requirement: release 安装器 MUST 自动执行 bootstrap 且失败仅告警
系统 MUST 在 release 安装器解压后自动执行一次 bootstrap；bootstrap 非零返回 MUST 仅告警，不阻断安装完成态。

#### Scenario: installer bootstrap failure is warning-only
- **WHEN** 安装器自动执行 bootstrap 且命令返回非零
- **THEN** 安装器输出明确 warning 与排障指引
- **AND** 安装流程保持完成态（不回滚已解压内容）

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
