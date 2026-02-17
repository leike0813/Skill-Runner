## 1. 配置重构

- [x] 1.1 定义并公开统一配置键 `session_timeout_sec`
- [x] 1.2 设置默认值为 `1200` 秒并增加合法性校验
- [x] 1.3 实现统一解析函数，输出归一化会话超时值

## 2. 兼容与优先级

- [x] 2.1 对历史键（如 `interactive_wait_timeout_sec` / `hard_wait_timeout_sec`）提供兼容映射
- [x] 2.2 定义冲突优先级：`session_timeout_sec` 优先
- [x] 2.3 增加 deprecation 日志，标记旧键即将移除

## 3. 消费位点统一

- [x] 3.1 Orchestrator 统一用归一化值计算 `wait_deadline_at`
- [x] 3.2 进程管理统一用归一化值执行超时终止
- [x] 3.3 持久化记录 run 级 effective timeout
- [x] 3.4 可观测接口/日志增加 effective timeout 展示

## 4. 测试与文档

- [x] 4.1 单测：未配置时默认值为 `1200`
- [x] 4.2 单测：新键覆盖默认值生效
- [x] 4.3 单测：仅旧键存在时兼容映射生效
- [x] 4.4 单测：新旧键冲突时新键优先
- [x] 4.5 集成：sticky_process 超时链路使用统一配置值
- [x] 4.6 文档：移除 interactive 专用 timeout 命名，仅保留 `session_timeout_sec`
