## 1. 协议与模型

- [x] 1.1 定义 `EngineSessionHandle` 数据结构与持久化字段
- [x] 1.2 定义 `EngineResumeCapability` 与 `EngineInteractiveProfile` 结构
- [x] 1.3 将恢复失败/等待超时/进程丢失错误码纳入统一错误模型
- [x] 1.4 接入统一会话超时归一化读取接口（命名/兼容由 `interactive-11` 统一收敛）

## 2. 能力探测与分层

- [x] 2.1 在引擎管理层实现 resume 静态能力探测
- [x] 2.2 在 interactive 首回合前执行动态 probe
- [x] 2.3 probe 成功标记 `resumable`，失败标记 `sticky_process`（不拒绝 interactive）

## 3. 三引擎恢复实现

- [x] 3.1 Codex：实现 session_id 提取与 `exec resume` 路径
- [x] 3.1.1 Codex：在 `--json` 输出中解析首条 `thread.started.thread_id` 并持久化为 handle
- [x] 3.1.2 Codex：构造 resume 命令时将 `thread_id` 作为位置参数放在 prompt 前
- [x] 3.2 Gemini：实现 `session_id` 提取与 `--resume` 路径
- [x] 3.2.1 Gemini：在 JSON 模式首轮返回体中解析 `session_id` 并持久化为 handle
- [x] 3.2.2 Gemini：恢复回合命令追加 `--resume "<session_id>"`
- [x] 3.3 iFlow：按 probe 结果支持 `resumable` 与 `sticky_process` 双路径
- [x] 3.3.1 iFlow resumable：在 `<Execution Info>` 中解析 `session-id` 并持久化为 handle
- [x] 3.3.2 iFlow resumable：恢复回合命令追加 `--resume "<session-id>"`
- [x] 3.3.3 iFlow sticky_process：保留进程驻留等待，不执行跨进程 resume

## 4. Orchestrator 集成

- [x] 4.1 进入 `waiting_user` 前持久化 `interactive_profile.kind`
- [x] 4.2 resumable：reply 后使用 handle 启动新进程恢复回合
- [x] 4.3 sticky_process：等待阶段持久化 `wait_deadline_at` 与进程绑定信息
- [x] 4.4 sticky_process：reply 在时限内路由回原进程；超时终止进程并失败

## 5. 测试与文档

- [x] 5.1 单测：三引擎 capability 探测成功/失败分支及 profile 映射
- [x] 5.2 集成：resumable 路径 ask -> waiting -> reply -> resume 跨进程闭环
- [x] 5.3 集成：sticky_process 路径 ask -> waiting(进程驻留) -> reply 闭环
- [x] 5.4 文档：补充三引擎恢复前提与错误处理建议
- [x] 5.5 单测：Codex `thread.started` 事件缺失时返回 `SESSION_RESUME_FAILED`
- [x] 5.6 单测：Gemini JSON 返回缺失 `session_id` 时返回 `SESSION_RESUME_FAILED`
- [x] 5.7 单测：iFlow resumable 路径 `<Execution Info>` 缺失 `session-id` 时返回 `SESSION_RESUME_FAILED`
- [x] 5.8 单测：sticky_process 超时返回 `INTERACTION_WAIT_TIMEOUT`
- [x] 5.9 单测：sticky_process 进程意外退出返回 `INTERACTION_PROCESS_LOST`
