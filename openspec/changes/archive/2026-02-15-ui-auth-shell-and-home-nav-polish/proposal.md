## Why

当前 Skill Runner 的 Engine 鉴权在容器中可通过 `docker exec` 较容易完成，但在本地部署场景下，用户经常需要手动切换到 managed 环境、复制凭证文件或反复试错，操作成本高且不透明。

同时，UI 首页中“Engine 管理 / Run 观测”入口仍为简单文本链接，信息层次和可发现性较弱。

为降低鉴权门槛并改善 UI 导航体验，本变更将引入受控的网页内鉴权终端能力，并同步优化首页入口展示。

## What Changes

1. 新增 UI 鉴权终端能力（/ui 下）
   - 在网页中提供一个受控 Shell 会话入口，运行在 Skill Runner 的 managed 环境。
   - 仅允许执行预置白名单命令（不开放任意命令输入）。
   - 全局同一时刻仅允许 1 个鉴权会话。
   - 支持 Linux/macOS/Windows 本地部署与容器部署一致行为。

2. 新增会话安全与可观测约束
   - 会话具备 idle timeout / TTL / 强制结束机制。
   - 会话输出流式展示（stdout/stderr）。
   - 记录最小审计信息（会话开始、结束、命令类型、退出码）。

3. UI 首页入口美化
   - 将首页文本超链接升级为卡片化入口（Engine 管理 / Run 观测）。
   - 保持无前端构建链（继续使用 Jinja2 + htmx）。

4. 依赖与文档同步
   - 为 Windows 交互终端引入 `pywinpty` 运行时依赖。
   - 在 README 与部署文档中明确该依赖用途与平台说明。

## Impact

- 受影响模块：
  - `server/routers/ui.py`
  - `server/services/*`（新增 UI shell 会话管理）
  - `server/assets/templates/ui/*`
  - `pyproject.toml`
  - `README.md` / `README_CN.md` / `docs/containerization.md`（或等价部署文档）
- 安全边界：
  - 仅预置命令；不提供任意命令执行能力。
  - UI Basic Auth 仍是访问前置条件。
