## Context

当前系统已具备：

- managed runtime 环境注入（`RuntimeProfile.build_subprocess_env`）；
- Engine 命令解析（`AgentCliManager.resolve_engine_command`）；
- UI 基础鉴权（`require_ui_basic_auth`）；
- Jinja2 + htmx 的页面渲染体系。

本变更目标是在不引入高风险远程命令执行面的前提下，提供“网页内可操作的鉴权终端”。

## Goals

1. 用户可在 `/ui` 中直接启动 Engine 鉴权会话（使用 managed 环境）。
2. 会话行为在本地/容器、Linux/macOS/Windows 下尽量一致。
3. 严格约束为白名单命令与单会话模型。
4. UI 首页导航可读性与可发现性提升。

## Non-Goals

- 不提供通用 Web SSH/任意 Shell。
- 不支持多并发会话。
- 不在本变更中实现基于角色的细粒度权限系统（沿用 UI Basic Auth）。

## Architecture

### 1) 新增 `UiShellManager`（服务层）

职责：

- 管理唯一活动会话（create/get/close）。
- 维护会话状态：`queued/running/closed/error/timeout`。
- 启动子进程并桥接 stdout/stderr 流。
- 维护 ring buffer（供前端拉取增量输出）。
- 超时治理：idle timeout + hard TTL。
- 记录审计事件（结构化日志）。

关键策略：

- **全局锁**：同一时刻只允许 1 个活跃会话。
- **白名单命令映射**（示例）：
  - `codex_login`
  - `gemini_login`
  - `iflow_login`
  - `codex_version`
  - `gemini_version`
  - `iflow_version`
- 前端传的是命令 ID，不是原始 shell 字符串。

### 2) 路由层（`server/routers/ui.py`）

新增：

- `/ui/engines/auth-shell` 页面入口。
- 会话控制接口（创建/关闭/状态读取）。
- 会话输出增量读取接口（HTTP polling + cursor）。

鉴权：

- 继续复用 `dependencies=[Depends(require_ui_basic_auth)]`。

### 3) 前端页面（Jinja2 模板）

新增 `engine_auth_shell.html`：

- 终端输出窗口（只读）；
- 命令选择器（预置命令）；
- “启动会话 / 结束会话”按钮；
- 状态提示（运行中、超时、已结束、失败原因）。
- 定时轮询会话状态与输出增量（cursor）。

首页 `index.html`：

- 将纯文本入口改为卡片入口（保持无构建流程）。

## Cross-Platform Considerations

### Linux/macOS

- 优先使用 PTY（若环境支持）实现更自然的交互显示。

### Windows

- 使用 `pywinpty` 提供 ConPTY 能力，确保本地部署可交互。
- 若 `pywinpty` 不可用，服务必须返回明确错误并提示安装依赖。

## Security

1. 命令输入面收敛到命令 ID（白名单），拒绝任意命令。
2. 会话默认工作目录固定在运行时安全目录（非用户任意路径）。
3. 会话超时自动清理，避免悬挂进程。
4. 记录审计日志：命令 ID、engine、会话 ID、开始/结束时间、退出码。

## Failure Handling

- 会话创建冲突：返回可识别错误（busy）。
- 子进程启动失败：会话进入 `error` 并回传错误文本。
- 轮询中断：前端可继续以最新 cursor 拉取增量输出。
- 超时触发：强制终止进程并标记 `timeout`。

## Testing Strategy

1. 单元测试：
   - 单会话互斥；
   - 白名单校验；
   - 超时清理；
   - Windows 依赖缺失的错误路径。
2. 路由测试：
   - 未鉴权访问被拒绝；
   - 会话状态接口行为；
   - busy 场景返回码与消息。
3. UI 回归：
   - 首页入口卡片渲染；
   - Engine Auth Shell 页面基础加载与状态提示。

## Documentation Updates

必须更新：

- `README_CN.md` / `README.md`：
  - 新增“网页内鉴权终端”说明；
  - 说明 Windows 需要 `pywinpty`。
- 部署文档（如 `docs/containerization.md`）：
  - 标注该依赖的用途与平台差异；
  - 给出依赖缺失时的排查建议。
