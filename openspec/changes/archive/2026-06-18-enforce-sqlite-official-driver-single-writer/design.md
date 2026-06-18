# Design

## SQLite handle registry
新增进程内 registry，以 resolved DB path 为 key 返回唯一 `SQLiteDbHandle`。每个 handle 持有一个官方 `aiosqlite.Connection` 和一个 `asyncio.Lock`。调用方通过 operation context 获取连接；context 退出时释放 operation lock，但不关闭连接。

## Store integration
`RunStoreDatabase.connect()` 继续保留 `async with` 形态，但实际委托 registry operation。已有 store 方法无需改变调用方式，同时同一 DB 文件的多语句操作会在同一 operation lock 内完成。

同步遗留 store 通过 sync bridge 调用 registry operation，避免在调用线程直接执行 `sqlite3.connect()`。这保留现有同步 API，同时把 SQLite 连接集中到官方 `aiosqlite` handle。

## Engine status cache
Engine status 的 API/UI getter 保持内存读取。持久化 load/refresh 使用 registry operation，失败时降级为内存快照，不阻塞请求热路径。

## Shutdown
应用 shutdown 调用 sync bridge close 和 registry close_all。关闭失败只记录 warning，不无限阻塞服务退出。

## Regression guard
增加测试确认 `aiosqlite_compat` 不含自研 executor/retry，并确认生产路径没有新增直接 `sqlite3.connect()`。
