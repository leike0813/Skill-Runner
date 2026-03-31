## Context

现有成功标准分两层：

1. adapter / stream parser 从 stdout/stream 提取结构化 payload；
2. lifecycle 对 payload 做 `__SKILL_DONE__` 剥离、schema 校验、artifact 归一化，再决定成功或失败。

这条链路已经有 deterministic generic repair，但 repair 只处理“文本中能否抽出 JSON 对象”，不能恢复“JSON 根本不在 stdout，而是在工作目录里由脚本正确落盘”的情况。

本次实现已经证明，最合适的接入点不是 adapter，而是 lifecycle：

- 需要访问 `run_dir`
- 需要读取 skill manifest 中的自定义结果文件名
- 需要复用现有 output schema 校验和 artifact autofix
- 不能干扰 `waiting_user` / `waiting_auth` 这类非终态输出分支

## Goals / Non-Goals

**Goals:**
- 为 `exit_code == 0` 的 run 增加最后一层结果恢复能力
- 允许 skill 用脚本稳定写出最终结果 JSON，而不必完全依赖 agent 最后一条消息
- 保持现有 stdout/stream 结构化输出为主路径，文件扫描只做兜底

**Non-Goals:**
- 不把结果文件恢复下沉到 adapter 层
- 不扩展到 ask-user、auth challenge、waiting_* 非终态 payload
- 不支持路径模板、目录路径或 glob，只支持文件名

## Decisions

### 1. 兜底触发点放在 lifecycle 结构化输出判定之后

只有在以下条件同时满足时才触发：

- `result.exit_code == 0`
- 没有 high-confidence auth 接管
- 没有 pending interaction / ask_user 接管
- 主路径没有得到合法最终输出，具体包括：
  - 无法解析出 JSON 对象
  - 解析出了对象，但 schema 校验失败

这保证文件恢复只修复终态成功输出，不改变 interactive / auth 生命周期。

### 2. 文件名声明挂在 `runner.json.entrypoint.result_json_filename`

现有 `entrypoint` 已经是开放字典，且用于放 prompt / entrypoint 级运行约束。把结果文件名放在这里有三个好处：

- 不需要再新增一层 manifest model 结构
- 能和 skill 的“最终如何交付结果”语义放在一起
- package validator / registry / management detail 都能自然透传

默认值仍固定为 `<skill-id>.result.json`。

### 3. 多候选按最新 `mtime` 选取

扫描 `run_dir` 递归子树时：

- 排除 `result/**` 和 `.audit/**`
- 只按 basename 精确匹配
- 多候选时优先 `mtime` 最新
- 若 `mtime` 相同，则按相对路径深度最浅优先
- 若仍相同，则按相对路径字典序最小

这样既符合“最后落盘的结果更可信”的直觉，也保留了稳定 tie-break。

### 4. 文件恢复不引入新的 `repair_level`

`repair_level` 目前只表达 adapter 层 JSON 解析修复。结果文件恢复属于 orchestrator 级恢复，不应混进同一维度。

因此恢复结果通过 warning / diagnostic 表达：

- `OUTPUT_RECOVERED_FROM_RESULT_FILE`
- `OUTPUT_RESULT_FILE_MULTIPLE_CANDIDATES`
- `OUTPUT_RESULT_FILE_INVALID_JSON`
- `OUTPUT_RESULT_FILE_SCHEMA_INVALID`
- `OUTPUT_RESULT_FILE_DECLARED_NOT_FOUND`

## Risks / Trade-offs

- [Risk] skill 误把临时 JSON 文件命名成结果文件名，导致被错误恢复。  
  -> Mitigation: 仅在主路径失败时触发；同时要求结果文件必须通过 output schema。

- [Risk] 多候选选择带来不透明性。  
  -> Mitigation: 明确 `mtime -> depth -> lexicographic` 选择规则，并记录多候选 warning。

- [Risk] interactive / auth 场景被结果文件错误覆盖。  
  -> Mitigation: 只有在 `ask_user` / auth 未接管时才允许触发恢复，并用回归测试锁住。
