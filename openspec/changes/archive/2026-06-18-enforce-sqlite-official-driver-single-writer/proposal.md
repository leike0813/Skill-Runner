# SQLite 官方驱动与单写者队列治理

## Summary
- 使用官方 `aiosqlite` 作为 SQLite driver，不再维护自研 executor/retry wrapper。
- 为每个 SQLite DB 文件建立进程内唯一 long-lived connection 和 operation lock。
- 保留现有拆库设计，但同一 DB 文件内所有读写都经同一 handle 串行执行。
- 清理生产热路径中的同步 `sqlite3.connect()`，避免主事件循环被 SQLite 全局锁阻塞。

## Motivation
服务曾在 `/ui/engines` 等请求中因同步 SQLite 连接打开卡住主事件循环；同时后台自研 SQLite executor 线程也卡在连接打开路径。拆库只能降低文件锁争用，不能避免同进程多线程多连接触发 SQLite 全局锁问题。

## Goals
- 请求热路径不得直接同步打开 SQLite 连接。
- 同一 DB 文件在进程内只有一个官方 `aiosqlite` connection/operation queue。
- 现有 `RunStore` facade 和 HTTP API 行为不变。
- shutdown 能统一关闭 SQLite handles。

## Non-Goals
- 不切换 PostgreSQL。
- 不引入 ORM 或迁移框架。
- 不改变对外 API 字段。
