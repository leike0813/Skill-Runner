## Why

当前核心请求链路是 async，但 4 个 SQLite store 仍使用同步 `sqlite3`，在高并发下会阻塞事件循环。  
这些 store 已覆盖编排、交互、观测、安装、临时 skill、引擎升级等主路径，需要一次性全链路异步化而不是局部替换。

## What Changes

- 引入 `aiosqlite`，替换 4 个 store 中的同步 SQLite 调用。
- 将 store 方法签名统一改为 `async def`，并将调用方统一改为 `await`。
- 将 run observability / source adapter 的端口协议同步改为异步签名。
- 保持 SQL schema、表字段、JSON 编解码语义和业务状态流转不变。
- 增加测试门禁，防止迁移后的 store 回归到同步 `sqlite3`。

## Capabilities

### New Capabilities
- `async-sqlite-store-access`: SQLite store 与其调用链使用异步访问语义，避免事件循环阻塞。

### Modified Capabilities
- `interactive-run-lifecycle`: 交互等待与回复路径的存取链路改为异步调用，不改变状态机语义。
- `interactive-run-observability`: run 观测读取路径改为异步 store 端口，不改变事件与历史语义。
- `ephemeral-skill-lifecycle`: 临时 skill 请求状态持久化与清理链路改为异步调用，不改变生命周期语义。
- `engine-upgrade-management`: 升级任务持久化改为异步调用，不改变任务状态语义。

## Impact

- Affected code:
  - `server/services/orchestration/run_store.py`
  - `server/services/skill/skill_install_store.py`
  - `server/services/skill/temp_skill_run_store.py`
  - `server/services/engine_management/engine_upgrade_store.py`
  - `server/runtime/observability/*`
  - `server/services/orchestration/*`
  - `server/services/skill/*`
  - `server/services/engine_management/*`
  - `server/routers/*`
- Dependencies:
  - `pyproject.toml` 新增 `aiosqlite`
- Public API:
  - HTTP API: 无变化
  - runtime schema/invariants: 无变化
  - 内部 Python 方法签名：store / 端口改为 async
