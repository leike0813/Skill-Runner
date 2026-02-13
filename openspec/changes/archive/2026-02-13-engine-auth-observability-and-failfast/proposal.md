## Why

当前本地部署与容器部署在 Engine 鉴权可观测性上存在明显短板：用户难以确认服务实际使用的是 managed prefix CLI 还是系统全局 CLI，也难以判断当前鉴权状态是否有效。与此同时，任务执行链路缺少 fail-fast 机制，Agent 在鉴权阻塞时可能长期处于 running，导致客户端无限轮询。

## What Changes

- 新增 Engine 鉴权观测能力（API + UI + 本地/容器脚本），明确展示：
  - managed CLI 是否存在
  - 实际可执行路径（managed/global）
  - 凭证文件状态（仅白名单鉴权文件）
- 固化 iFlow managed 默认配置基线，并补充旧配置自动迁移：
  - `selectedAuthType = "oauth-iflow"`
  - `baseUrl = "https://apis.iflow.cn/v1"`
- 在鉴权诊断语义中明确：iFlow 的 auth-stuck 识别以前置“配置基线正确”为前提。
- 修复 `ensure` 安装判定：从“任意 PATH 可执行即视为已安装”改为“managed prefix 下存在才视为已安装”。
- 引入执行 fail-fast 策略：
  - 增加硬超时（默认 600s）
  - 超时后强制终止子进程并标准化错误
  - 基于真实输出样本进行 auth-stuck 识别（命中则归类 `AUTH_REQUIRED`，否则 `TIMEOUT`）
- 增加鉴权诊断脚本，支持本地和容器用户快速定位“卡鉴权/路径跑偏”问题。

## Capabilities

### New Capabilities
- `engine-auth-observability`: 提供统一的 Engine 鉴权状态可观测能力（API/UI/脚本），覆盖 managed 与 global 路径差异诊断。
- `engine-execution-failfast`: 为 Agent 子进程执行增加硬超时与鉴权阻塞识别，避免任务无限 running。

### Modified Capabilities
- `engine-upgrade-management`: 升级/ensure 对“已安装”判定改为 managed prefix 强约束，避免被全局 CLI 误判短路。

## Impact

- 受影响代码：
  - `server/services/agent_cli_manager.py`
  - `server/adapters/base.py`
  - `server/services/job_orchestrator.py`
  - `server/routers/engines.py`
  - `server/routers/ui.py` 与 UI 模板
  - `scripts/` 下鉴权诊断脚本
- 受影响配置：
  - 新增执行硬超时配置项（默认 600s，支持环境变量覆盖）
  - iFlow managed 默认设置基线（auth type/baseUrl）与 legacy 自动迁移
- 受影响测试：
  - auth 状态接口与 UI 回显测试
  - managed/global 判定测试
  - fail-fast 与错误归类测试
