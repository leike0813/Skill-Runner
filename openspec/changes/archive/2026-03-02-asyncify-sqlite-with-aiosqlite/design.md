## Context

当前系统大部分请求链路已是 async，但关键 SQLite store 仍使用同步 `sqlite3`。  
这些 store 被路由层、编排层、观测层和后台任务广泛调用，形成“async 入口 + sync DB I/O”混合形态，存在事件循环阻塞风险。

## Goals / Non-Goals

**Goals:**
- 将 4 个 SQLite store 全量迁移为 `aiosqlite` 异步访问。
- 将调用链统一改为 `async/await`，不保留同步兼容壳。
- 保持 HTTP API、runtime schema/invariants、状态机语义和表结构语义不变。
- 增加门禁测试，防止回归到同步 sqlite 访问。

**Non-Goals:**
- 不更换数据库类型，不引入 ORM，不改业务状态机。
- 不重构非 SQLite 相关模块职责。
- 不改变外部路由协议与响应字段。

## Decisions

### 1) 连接模型：每次操作独立连接
- Decision: 采用 per-operation connection（每个 store 方法内部 `aiosqlite.connect`）。
- Rationale: 最小化生命周期管理复杂度，符合现有 store 调用模式，迁移风险最低。
- Alternative: 长连接/连接池。Rejected，因为 sqlite 单文件 + 当前负载模式下收益有限且会增加线程/生命周期复杂度。

### 2) 初始化策略：懒初始化 + 锁保护
- Decision: 每个 store 增加 `_ensure_initialized()`，使用 `asyncio.Lock` 与布尔标志控制一次性初始化。
- Rationale: 避免 import 时执行 DB I/O，同时保证并发首次访问时初始化与迁移幂等。
- Alternative: 在 `__init__` 中同步初始化。Rejected，因为与纯异步目标冲突。

### 3) 接口策略：端口协议同步切为 async
- Decision: `RunStorePort`、`RunSourceAdapter` 及相关 helper 统一切为 async 签名。
- Rationale: 防止“异步 store + 同步端口”造成桥接复杂度和漏 await 风险。
- Alternative: 保留同步协议并在内部桥接。Rejected，因为增加不可见阻塞与维护负担。

### 4) 调用链策略：一次性全链路切换
- Decision: 在同一 change 中同时改 store、service、router、tests。
- Rationale: 半迁移状态会导致接口不一致和大量临时兼容逻辑；一次切换更可控。
- Alternative: 分波仅改 run_store。Rejected，因为其它 store 同样位于 async 路径且改造模式一致。

### 5) 兼容策略：语义不变，仅 I/O 风格变化
- Decision: SQL、字段、状态更新时机、错误映射保持原语义；仅替换调用方式为 await。
- Rationale: 降低行为回归风险，保持既有合同与测试基线。

## Risks / Trade-offs

- [Risk] 大量调用点改造容易遗漏 `await`  
  → Mitigation: 全仓 grep 校验 + 关键回归测试 + mypy。
- [Risk] 背景任务与同步函数混用导致 coroutine 未执行  
  → Mitigation: 将相关后台入口函数改为 async callable，并以测试覆盖。
- [Risk] 并发初始化期间迁移重复执行  
  → Mitigation: store 内部 `_ensure_initialized()` + 锁串行化初始化路径。
- [Risk] monkeypatch 测试桩失配  
  → Mitigation: 测试统一改为 async stub / `AsyncMock`。

## Migration Plan

1. 修改依赖，新增 `aiosqlite`。
2. 改造 4 个 store（含初始化与迁移逻辑）。
3. 改造 runtime observability / source adapter 协议与实现。
4. 改造 orchestration/skill/engine 服务调用链。
5. 改造 routers 调用链。
6. 改造测试与新增边界门禁。
7. 运行 pytest + runtime 合同测试 + mypy，确认全绿。

## Open Questions

- 无。当前设计决策已锁定为“全链路纯异步 + 语义兼容优先”。

