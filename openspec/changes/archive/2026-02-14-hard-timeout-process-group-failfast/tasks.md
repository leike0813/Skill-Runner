## 1. Timeout 进程终止链路

- [x] 1.1 在基类适配器引入跨平台进程组创建参数
- [x] 1.2 实现 timeout 下的进程组两阶段终止（soft/hard kill）
- [x] 1.3 为读流任务增加有界收尾，避免 gather 长时间阻塞

## 2. 终态判定与缓存约束

- [x] 2.1 在 `JobOrchestrator` 中实现 `failure_reason` 失败优先级
- [x] 2.2 明确 timeout/auth_required 场景不入 cache
- [x] 2.3 timeout 错误文案使用“本次实际生效的 timeout 值”

## 3. 测试

- [x] 3.1 补充适配器 fail-fast 单测（timeout 返回与收敛性）
- [x] 3.2 补充 orchestrator 单测（timeout 优先失败、不入 cache、保留 artifacts）
- [x] 3.3 运行相关单测与 mypy
