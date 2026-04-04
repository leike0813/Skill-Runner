## 1. OpenSpec

- [x] 1.1 创建 `single-worker-hotpath-async-audit-and-auth-windowing` change 工件
- [x] 1.2 补齐 proposal / design / delta spec

## 2. Runtime hot path

- [x] 2.1 为 `stdout.log` / `stderr.log` / `io_chunks` 引入后台 writer
- [x] 2.2 为 FCMP / RASP / chat replay audit mirror 引入后台 writer
- [x] 2.3 将 slot 释放与 bounded audit drain 解耦

## 3. Auth detection

- [x] 3.1 改为最近窗口探测，移除全文 join 依赖
- [x] 3.2 将 probe 节流降频到 `1.5s`
- [x] 3.3 保留终态强制 probe 兜底

## 4. Observability

- [x] 4.1 terminal protocol history 增加 bounded flush
- [x] 4.2 bounded flush 未完成时回退到 live-first，避免同步卡住

## 5. Validation

- [x] 5.1 增加/更新热路径与 observability 回归测试
- [x] 5.2 运行目标 pytest
- [x] 5.3 运行目标 mypy
