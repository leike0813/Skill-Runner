## 1. 协议与规格

- [x] 1.1 为 `interaction.reply.accepted` 增加 schema-backed 的 orchestrator event 定义。
- [x] 1.2 更新 proposal、design 和 delta specs，明确 canonical reply-accepted 发布路径。

## 2. Canonical 发布链路

- [x] 2.1 调整 interactive reply 提交逻辑：成功后追加 `interaction.reply.accepted` orchestrator event，而不是直接发布 FCMP。
- [x] 2.2 扩展 orchestrator-event-to-FCMP 翻译，产出 `interaction.reply.accepted` 及配对的 `conversation.state.changed(waiting_user->queued)`。

## 3. Chat Replay 集成

- [x] 3.1 保持 canonical chat replay 继续从 FCMP `interaction.reply.accepted` 派生普通用户回复气泡。
- [x] 3.2 确保 `/chat` 和 `/chat/history` 在无 interaction-history fallback 的前提下仍能显示已接受的用户回复。

## 4. 验证

- [x] 4.1 增加 `interaction.reply.accepted` 的 schema、translator 和 chat replay 回归测试。
- [x] 4.2 运行 runtime protocol、chat replay 相关测试以及本次改动文件的定向类型检查。
