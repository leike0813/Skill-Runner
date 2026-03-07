## 1. Terminal 错误摘要入流

- [x] 1.1 扩展 `lifecycle.run.terminal` schema（`code/message` 可选）
- [x] 1.2 lifecycle 终态写入统一携带 `code/message(summary)`
- [x] 1.3 FCMP live translate 与 history replay 优先使用 terminal 摘要
- [x] 1.4 `error.run.failed` 的 FCMP 映射收敛为 diagnostic warning

## 2. runtime.dependencies 注入链路

- [x] 2.1 adapter 执行前实现 `uv` 注入探测
- [x] 2.2 探测成功走 `uv run --with ...` 包装
- [x] 2.3 探测失败记录 warning 并回退原命令（best-effort）
- [x] 2.4 run lifecycle 将该 warning 写入诊断与审计事件

## 3. SSOT / 文档同步

- [x] 3.1 更新 OpenSpec 主 specs（job-orchestrator-modularization / interactive-job-api）
- [x] 3.2 更新 runtime schema 合同文档与协议说明
- [x] 3.3 更新 adapter design 对 runtime.dependencies 的执行语义

## 4. 测试

- [x] 4.1 新增 terminal 摘要映射与去重回归测试
- [x] 4.2 新增 runtime.dependencies 注入成功/失败单测
- [x] 4.3 新增 orchestrator warning 落盘回归测试
- [x] 4.4 运行 runtime 合同测试与关键回归
