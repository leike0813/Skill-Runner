# 设计

## 1. 判定链路重构
interactive 模式的回合结束判定收敛为以下顺序：

1. `done marker`
2. `ask_user` 证据
3. 标准化 JSON 提取
4. schema / artifact 修复校验
5. 状态归一化

该顺序必须由 lifecycle 单点消费，repair 不得再参与“是否完成”的识别。

## 2. ask_user 证据优先级
`<ASK_USER_YAML>` 是最高优先级证据，其次是显式 `turn_result.ask_user` 与其他结构化 interaction payload。

一旦当前 attempt 命中 ask-user 证据：

- 当前回合不得进入 `succeeded`；
- generic JSON repair 不得将其改判为 final；
- 生命周期必须转入 `waiting_user`。

## 3. soft completion 保留但收紧
interactive 继续允许 soft completion，但只在以下条件同时满足时成立：

- 未命中 `__SKILL_DONE__`；
- 未命中 ask-user 证据；
- 成功提取标准化 JSON；
- output schema 校验通过；
- best-effort artifact 修复后仍然成立。

若提取到 JSON 但 schema 校验未通过，run 不再进入 `failed`，而是进入 `waiting_user` 并产出 warning。

若既没有 ask-user 证据，也没有可提取 JSON，同样进入 `waiting_user`。

## 4. JSON 提取与 repair 边界
允许的 structured output 来源收敛为：

- 显式 `turn_result.final_data`
- 受限的 assistant message 文本提取

对 assistant message 文本提取增加约束：

- 当前 attempt 未命中 ask-user 证据；
- 只能提取最外层候选结果；
- 正文中的证据数组、示例片段、 fenced JSON 子对象不得直接提升为 final payload。

repair 仅用于修复已经进入 soft completion 候选的 payload / artifact path，不得改变“当前回合是否完成”的状态判定。

## 5. Warnings / diagnostics
新增并统一以下 warning / diagnostic：

- `INTERACTIVE_SOFT_COMPLETION_SCHEMA_TOO_PERMISSIVE`
- `INTERACTIVE_OUTPUT_EXTRACTED_BUT_SCHEMA_INVALID`
- `INTERACTIVE_SOFT_COMPLETION_SUPPRESSED_BY_ASK_USER`

这些告警需要进入：

- `result/result.json`
- `.audit/meta.<attempt>.json`
- RASP `diagnostic.warning`
- FCMP 对应 diagnostic 映射

## 6. SSOT 门禁
本次实现顺序固定为：

1. 更新 `runtime_contract` / statechart / FCMP sequence / invariants / OpenSpec specs
2. 先让合同与不变量测试通过
3. 再修改 lifecycle、interaction 和 parser / repair 边界实现
4. 最后更新行为测试与回归测试
