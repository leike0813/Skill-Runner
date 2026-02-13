## Context

在运行时完全隔离（managed prefix + isolated agent home）上线后，出现两个现实问题：

1. 用户无法快速判断“服务当前到底在用哪套 CLI 与鉴权凭证”；
2. 子进程在鉴权阻塞时缺少终止与归类策略，导致任务长期 running。

此外，`ensure` 当前会被全局 CLI 可执行路径误判，导致 managed prefix 下某些引擎未安装却被跳过（已在 iflow 复现）。
以及 iFlow 在 managed 环境下如果仅有旧式最小 settings（`selectedAuthType=iflow` 且缺 `baseUrl`）会触发 `Invalid URL`，掩盖真实鉴权状态并干扰 fail-fast 归类。

## Decisions

### 1) 鉴权可观测性：三端一致输出（API/UI/脚本）

- 新增统一 auth 诊断结构（按 engine）：
  - `managed_present`: managed prefix 下是否存在可执行文件
  - `effective_cli_path`: 服务实际将调用的路径
  - `effective_path_source`: `managed | global | missing`
  - `credential_files`: 白名单鉴权文件存在性明细
  - `auth_ready`: 鉴权就绪的保守判定（仅静态）
- 暴露渠道：
  - API：`GET /v1/engines/auth-status`
  - UI：`/ui/engines` 增加鉴权状态与路径来源显示
  - 脚本：`scripts/check_agent_auth.sh` / `scripts/check_agent_auth.ps1`
- 对 iFlow 增加配置基线保障：
  - 初始化/检查时确保 managed `~/.iflow/settings.json` 至少包含：
    - `selectedAuthType = "oauth-iflow"`
    - `baseUrl = "https://apis.iflow.cn/v1"`
  - 若检测到 legacy 配置（如 `selectedAuthType=iflow` 或 `baseUrl` 缺失/非法），自动迁移为基线值。

### 2) managed 安装判定修复

- `ensure` 安装逻辑以 `managed_present` 为准，不再以“PATH 上任意可执行”短路。
- 保留 `global_available` 仅用于诊断提示，不用于 `ensure` 决策。

### 3) fail-fast 策略（默认 hard timeout = 600s）

- 在 adapter 基类执行层引入硬超时：
  - 超时后终止子进程（terminate -> kill）
  - 保留并落盘已捕获 stdout/stderr
- 错误归类：
  - 若输出命中 auth-stuck 规则 -> `AUTH_REQUIRED`
  - 否则 -> `TIMEOUT`
- no-output timeout 本次不启用，避免误伤长静默任务。

### 4) auth-stuck 规则来源

- 使用已采样的真实输出作为规则基线：
  - Gemini：授权 URL + authorization code 提示
  - Codex：401 Unauthorized / Missing bearer
  - iFlow：`SERVER_OAUTH2_REQUIRED`（在配置基线正确前提下）
- 规则放在可维护位置（配置常量），便于后续增量更新。

## Error Model

- `AUTH_REQUIRED`：明确识别到未鉴权/需登录语义
- `TIMEOUT`：达到硬超时但未命中 AUTH_REQUIRED
- 两者都进入 run `FAILED` 终态，避免无限轮询。

## Testing Strategy

- 单元测试：
  - managed/global 判定分支
  - 鉴权状态 API 返回结构
  - auth-stuck 规则匹配
  - hard timeout 后错误归类
- 集成测试：
  - 使用可控假进程输出模拟 AUTH_REQUIRED/TIMEOUT 路径
- 人工验证：
  - 通过诊断脚本确认本地与容器输出一致。
