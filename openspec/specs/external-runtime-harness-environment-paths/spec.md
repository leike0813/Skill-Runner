# external-runtime-harness-environment-paths Specification

## Purpose
TBD - created by archiving change interactive-41-external-runtime-harness-conformance. Update Purpose after archive.
## Requirements
### Requirement: Harness MUST 默认继承本地部署同源环境语义
系统 MUST 默认复用与本地部署脚本一致的 managed prefix 相关环境语义，包括数据目录、agent cache、agent home、npm prefix 与 uv 路径。

#### Scenario: 默认环境值与本地部署语义一致
- **WHEN** 用户未显式提供 harness 环境覆盖
- **THEN** harness 读取并使用与本地部署同源的 managed prefix 相关环境变量
- **AND** 执行路径优先使用 managed prefix 下的引擎二进制

### Requirement: Harness MUST 将 run root 默认重定向到独立目录
系统 MUST 将 harness 运行目录默认写入 `data/harness_runs/`，并与主服务 `data/runs/` 隔离。

#### Scenario: 默认写入 harness_runs
- **WHEN** 用户执行 harness start/resume 且未指定 run root 覆盖
- **THEN** 新 run 目录创建在 `data/harness_runs/`
- **AND** 主服务 `data/runs/` 不被写入 harness run 数据

### Requirement: Harness MUST 支持 run root 环境变量覆盖
系统 MUST 支持通过环境变量覆盖 harness 默认 run root，用于在不同本地环境下重定向数据位置。

#### Scenario: 环境变量覆盖生效
- **WHEN** 用户设置 harness run root 覆盖环境变量
- **THEN** harness 在覆盖路径创建并管理 run 目录
- **AND** 相关审计与报告工件写入覆盖路径

### Requirement: Harness MUST 保持对 managed prefix 的复用而非重建
系统 MUST 优先复用本地部署后已存在的 managed prefix 环境，不得默认创建新的独立 CLI 安装前缀。

#### Scenario: 复用已有 managed prefix
- **WHEN** managed prefix 中已存在目标引擎可执行文件
- **THEN** harness 直接复用该可执行文件
- **AND** 不额外创建第二套默认 npm prefix

### Requirement: Harness MUST 提供环境自检与失败可诊断性
系统 MUST 在启动前执行关键路径与可执行文件自检，并在失败时输出结构化诊断信息。

#### Scenario: 缺失可执行文件时结构化报错
- **WHEN** 目标引擎在 managed prefix 中不可执行或缺失
- **THEN** harness 返回结构化错误并包含缺失路径信息
- **AND** 错误类型可被脚本化识别用于 CI 失败判定

### Requirement: Harness 环境隔离 MUST 不污染引擎全局用户目录
系统 MUST 保持运行时隔离环境（如 HOME/XDG 指向 managed prefix 子路径），避免把 harness 运行状态写入宿主机全局用户目录。

#### Scenario: 运行状态落在 managed prefix 下
- **WHEN** harness 运行引擎命令
- **THEN** 引擎配置/状态写入 managed prefix 对应隔离目录
- **AND** 宿主机全局用户配置目录不被 harness 修改

### Requirement: Harness MUST 对 Codex/Gemini 注入并清理 run trust
系统 MUST 在 Codex/Gemini 运行前注入 run 目录 trust，并在本次运行结束后移除该 trust，保持与主服务执行链路一致。

#### Scenario: Codex/Gemini trust 生命周期与主服务一致
- **WHEN** harness 执行 `codex` 或 `gemini` 的 start/resume
- **THEN** 在引擎启动前注册当前 run 目录 trust
- **AND** 在运行结束后无论成功/失败均移除本次 run trust

### Requirement: Harness MUST 在运行前注入项目与夹具技能包
系统 MUST 在每次 attempt 启动前将技能包注入到 run 目录的引擎技能根，来源同时覆盖项目根 `skills/` 与 `tests/fixtures/skills/`。

#### Scenario: 同时注入项目技能与 fixtures 技能
- **WHEN** harness 启动一次引擎执行
- **THEN** 从 `<project_root>/skills/` 与 `<project_root>/tests/fixtures/skills/` 扫描技能目录并注入
- **AND** 注入目标路径按引擎映射到 `.codex/.gemini/.iflow/.opencode` 对应 `skills/` 目录

#### Scenario: 注入摘要可审计追踪
- **WHEN** harness 完成一次 attempt 并写入 meta 审计文件
- **THEN** meta 中包含 skill 注入摘要（source_roots、target_root、skill_count、skills）
- **AND** 注入缺失或空来源时仍输出结构化摘要（skill_count=0）

### Requirement: Harness MUST 在执行前注入与 API 同类的引擎工具配置
系统 MUST 在每次 attempt 执行命令前完成引擎工具配置注入，并将注入结果记录到审计 meta。

#### Scenario: 执行前配置注入成功并可追溯
- **WHEN** harness 启动一次 start 或 resume attempt
- **THEN** 在引擎命令执行前完成配置注入
- **AND** `.audit/meta.N.json` 中包含 `config_injection` 摘要（至少包含 engine、config_path）

#### Scenario: 配置注入失败时返回结构化错误
- **WHEN** 引擎配置注入阶段抛出异常
- **THEN** harness 返回 `ENGINE_CONFIG_INJECTION_FAILED`
- **AND** 错误细节包含引擎名与失败原因

### Requirement: Harness Codex 配置注入 MUST 使用独立 profile 名
系统 MUST 在 harness 链路中为 Codex 使用独立 profile 名，并与 API 默认 profile 隔离。

#### Scenario: Codex harness profile 与 API profile 隔离
- **WHEN** harness 执行 Codex 的 start 或 resume
- **THEN** Codex 配置注入目标 profile 名为 `skill-runner-harness`
- **AND** 不覆盖 API 链路默认 profile `skill-runner`

