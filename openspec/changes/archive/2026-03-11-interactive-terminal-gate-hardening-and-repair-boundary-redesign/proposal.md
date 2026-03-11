# Change 标题
`interactive-terminal-gate-hardening-and-repair-boundary-redesign`

## 背景
当前 interactive 终态判定过于宽松：

- `assistant` 文本中的内嵌 JSON 可能被 generic repair 误提取为最终输出；
- `<ASK_USER_YAML>` 虽然是高可信交互证据，但现行语义仍允许其被 soft completion 绕过；
- output schema 过宽松时，误提取结果容易通过校验并错误进入终态。

这会导致本应继续交互的 run 被错误判定为 `succeeded`。

## 本次变更
本次 change 先收口 SSOT，再实现：

1. 将 interactive 终态门禁重写为单一证据优先级状态机；
2. 明确 `<ASK_USER_YAML>` 为最高优先级证据，一旦命中即禁止 soft completion / repair 改判完成；
3. 保留 interactive soft completion，但收紧 JSON 提取来源与 repair 边界；
4. 对宽松 schema 与“提取 JSON 但校验失败”的情况增加明确 warning / diagnostic。

## 预期结果
- interactive run 不再因正文内嵌 JSON 被误判完成；
- ask-user turn 必然进入 `waiting_user`；
- soft completion 仅在没有 ask-user 证据、且标准化输出真正通过校验时成立；
- 生命周期、协议审计、文档和测试语义重新对齐。
