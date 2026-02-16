## 1. 状态机与存储

- [ ] 1.0 前置检查：`interactive-05-engine-session-resume-compatibility` 已完成并可提供统一 session handle
- [ ] 1.1 扩展 `RunStatus`，新增 `waiting_user`
- [ ] 1.2 在 `run_store` 增加交互状态、`interactive_profile` 与历史持久化表
- [ ] 1.3 增加 run_dir 下 `interactions/` 文件镜像写入

## 2. Orchestrator 重构

- [ ] 2.1 将 `run_job` 拆为“单回合执行 + 状态迁移”结构
- [ ] 2.2 实现 `running -> waiting_user` 转换与 pending 持久化
- [ ] 2.3 resumable：实现 reply 后恢复执行的入队逻辑
- [ ] 2.4 sticky_process：实现 reply 回注入驻留进程的继续执行逻辑

## 3. 并发槽位与超时策略

- [ ] 3.1 resumable：确保 `waiting_user` 前释放 slot
- [ ] 3.2 resumable：确保 resume 回合前重新申请 slot
- [ ] 3.3 sticky_process：确保 `waiting_user` 期间保持 slot，不提前释放
- [ ] 3.4 sticky_process：实现 `wait_deadline_at` 超时后终止进程并释放 slot
- [ ] 3.5 覆盖异常路径下 slot 必释放的回归测试

## 4. 测试

- [ ] 4.1 单测：resumable run 在 ask_user 后状态为 waiting_user 且 slot 释放
- [ ] 4.2 单测：resumable reply 后 run 可重新进入 running 并最终终态
- [ ] 4.3 单测：sticky_process run 在 waiting_user 期间保持 slot 且进程驻留
- [ ] 4.4 单测：sticky_process 超时后 run 失败并释放 slot
- [ ] 4.5 集成：resumable waiting_user 不阻塞后续任务
