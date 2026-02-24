## 1. Management API

- [x] 1.1 在 `run_observability` 增加 protocol history 读取入口（`fcmp|rasp|orchestrator`）
- [x] 1.2 新增管理路由 `GET /v1/management/runs/{request_id}/protocol/history`
- [x] 1.3 覆盖 stream 参数校验与 seq/time 过滤透传
- [x] 1.4 `protocol/history` 增加 `attempt` 参数与 `available_attempts` 返回
- [x] 1.5 `logs/range` 增加 `attempt` 参数并按轮次读取 `.audit/*.{attempt}.log`

## 2. Management UI

- [x] 2.1 从 `run_detail.html` 移除 pending/reply 表单与提交逻辑
- [x] 2.2 保留 FCMP 对话、raw stderr、raw_ref 预览、cancel
- [x] 2.3 新增 FCMP/RASP/orchestrator 审计面板并接入 protocol history
- [x] 2.4 新增 attempt 左右翻页控件，三类审计面板与 raw stderr 同步切换轮次
- [x] 2.5 重进页面先加载历史再接实时流

## 3. E2E Client

- [x] 3.1 增加 `BackendClient.get_run_final_summary(...)`
- [x] 3.2 新增 `GET /api/runs/{request_id}/final-summary`
- [x] 3.3 重构 `run_observe.html` 为对话气泡布局
- [x] 3.4 Ask User YAML 提取并转换为提示卡，不进入聊天气泡
- [x] 3.5 `user.input.required` 归类为 Agent 问询，按 `interaction_id + prompt` 去重
- [x] 3.6 新增 `Ctrl+Enter`/`Cmd+Enter` 发送快捷键
- [x] 3.7 终态 `has_result || has_artifacts` 时追加最终摘要气泡
- [x] 3.8 完整下线 Replay（路由、入口、写入链路）
- [x] 3.9 `/runs` 页面改为以后端 runs 数据源渲染
- [x] 3.10 保留文件树能力为折叠区（默认收起）

## 4. Audit & Runtime

- [x] 4.1 协议审计文件改为按 attempt 分片（RASP/FCMP/orchestrator/diagnostics/metrics）
- [x] 4.2 停止写入聚合协议文件（`events.jsonl/fcmp_events.jsonl/orchestrator_events.jsonl/...`）
- [x] 4.3 停止创建/写入旧 `run_dir/logs` 与 `run_dir/raw`
- [x] 4.4 FS diff 忽略规则统一到 server + harness

## 5. Tests

- [x] 5.1 更新管理 UI 路由断言（移除 reply 控件、加入 attempt 语义）
- [x] 5.2 新增管理 protocol history attempt 路由单测
- [x] 5.3 新增 management logs/range attempt 单测
- [x] 5.4 新增 run_observability attempt 分片单测
- [x] 5.5 新增 server/harness FS diff 忽略规则单测
- [x] 5.6 更新 E2E 集成测试断言（Replay 下线、final-summary has_result）
- [x] 5.7 更新 E2E 观察页语义测试（YAML 提示卡/去重/摘要）

## 6. interactive-49 增补修复（协议+游标+回放）

- [x] 6.1 `chat_event.seq` 切换为跨 attempt 全局递增，`meta.local_seq` 保留本地序号
- [x] 6.2 修复 waiting_user 同文重复：`assistant.message.final` 与 `user.input.required` 去重
- [x] 6.3 `interaction.reply.accepted` 增加 `response_preview` 并仅发当前 attempt 对应回复
- [x] 6.4 orchestrator 事件写入 `seq`；旧数据读侧回填
- [x] 6.5 管理页 attempt 翻页控件移至“对话区/流观测区”之间
- [x] 6.6 E2E Result 页面下线，文件树并入 Observation 并固定双栏布局
- [x] 6.7 新增/更新单测：全局 seq、协议去重、orchestrator 回填、E2E 语义
- [x] 6.8 `fcmp_events.{attempt}.jsonl` 落盘 `seq` 全局化，`meta.local_seq` 持久化保留本轮序号
- [x] 6.9 修复续跑排序：`interaction.reply.accepted` 先于 resumed `assistant.message.final`
- [x] 6.10 E2E 隐藏 completion 气泡并抑制 `__SKILL_DONE__` 原始终态消息，终态仅保留 summary
