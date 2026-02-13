## Context

当前 Engine 管理链路存在两类耦合问题：

1. **模式耦合**：脚本默认目录假设偏容器（`/data`），本地运行时容易权限失败。
2. **环境耦合**：CLI 安装位置、命令解析路径与配置读取位置混杂，导致本地全局工具与服务运行上下文互相影响。

目标是把运行时抽象为“可解析配置”，在本地与容器里使用同一行为模型。

## Decisions

### 1) 引入统一运行时解析器（Runtime Profile Resolver）

- 新增统一解析逻辑，输出：
  - `runtime_mode`: `container | local`
  - `platform`: `linux | darwin | windows`
  - `data_dir`、`agent_cache_root`、`agent_home`、`npm_prefix`
  - 供子进程使用的标准环境变量集合
- 解析优先级：
  1. 显式环境变量覆盖
  2. 运行时自动检测（容器/本地，OS）
  3. 平台默认值

### 2) Managed Prefix 作为唯一受管安装位置

- Engine 安装/升级/检测统一使用 `npm --prefix <managed_prefix>`。
- CLI 调用优先使用 `<managed_prefix>/bin`（Windows 下对应 Scripts/bin 路径）。
- 不再依赖系统全局 `npm -g` 作为服务运行前提。

### 3) Agent 配置完全隔离 + 白名单凭证导入

- 服务默认使用独立 `agent_home`，并通过 `HOME`（及平台等价变量）注入到子进程。
- 新增“导入凭证”流程，**只导入鉴权文件，不导入 settings**：
  - Codex: `auth.json`
  - Gemini: `google_accounts.json`、`oauth_creds.json`
  - iFlow: `iflow_accounts.json`、`oauth_creds.json`
- 导入流程采用白名单复制，拒绝目录整体同步。

### 4) 全脚本路径策略统一

- 所有涉及目录读写的脚本改为通过运行时解析结果取值，移除硬编码兜底（尤其 `/data`）。
- `engine_upgrade_manager` 统一向脚本传入解析后的环境变量，保证脚本与服务侧一致。

### 5) 本地一键部署（Linux + Windows）

- 新增：
  - `scripts/deploy_local.sh`
  - `scripts/deploy_local.ps1`
- 责任边界：
  - 创建/校验本地目录
  - 检查 Node/npm/python 环境与可执行性
  - 初始化受管路径并给出启动命令（或直接启动）
- 不创建项目内虚拟环境，不引导 conda 命名环境依赖。

## Data & Path Strategy

- `data_dir` 与 `agent_cache_root` 强制分离。
- `agent_cache_root` 使用独立位置，避免因挂载 `data` 暴露缓存内部结构。
- Windows 本地默认路径使用 `%LOCALAPPDATA%` 族目录；Linux/macOS 使用用户数据目录（XDG/`~/.local/share`）。

## Risks & Mitigations

- **风险：PATH 顺序导致误用全局 CLI**
  - 缓解：调用时使用受管路径绝对可执行文件或显式前置 PATH。
- **风险：历史部署依赖旧目录结构**
  - 缓解：提供迁移说明与兼容读取（只读探测旧位置，写入走新位置）。
- **风险：Windows 路径差异引发脚本兼容问题**
  - 缓解：为 Windows 提供独立 PowerShell 脚本与路径单元测试。
