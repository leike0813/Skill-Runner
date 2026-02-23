## Context

现有实现中，常规 skill 链路已按 `execution_mode` 对缓存进行分流（`interactive` 不读写缓存），但临时 skill 链路仍采用“无条件 bypass cache”。  
该行为与当前产品期望不一致，并且若直接为临时链路打开缓存而不引入 skill 包内容因子，会引入跨包误命中风险。

## Goals / Non-Goals

**Goals:**
- 统一常规与临时 skill 链路缓存门禁：仅 `auto` 模式参与缓存，`interactive` 模式禁止 cache lookup/write-back。
- 为临时 skill auto 缓存引入稳定且可复现的“上传压缩包整体哈希”键因子。
- 保持 `runtime_options.no_cache=true` 的强制禁用优先级。
- 明确与 output repair 缓存语义的一致性，避免规范冲突。

**Non-Goals:**
- 不改变缓存存储后端、TTL、清理策略。
- 不引入跨版本缓存迁移工具。
- 不在本变更中新增缓存可视化页面。

## Decisions

### Decision 1: 缓存模式门禁统一为 auto-only
常规链路与临时链路统一执行以下规则：
- `execution_mode=interactive`：不进行 cache lookup，不进行 cache write-back；
- `execution_mode=auto`：允许缓存（仍受 `no_cache` 禁用）。

原因：
- interactive 回合包含用户对话上下文，不满足可复用前提；
- 与当前交互式运行语义一致，减少误命中与状态歧义。

### Decision 2: 临时 skill 缓存键必须包含上传压缩包哈希
对临时 skill 链路，cache key 在既有因子基础上新增：
- `temp_skill_package_hash`: 对用户上传的 skill 压缩包整体计算稳定哈希（建议 SHA-256）。

既有因子沿用常规链路：
- inline 输入规范化哈希
- 文件输入 manifest/hash
- parameter 哈希
- engine/runtime 选项（现有 key 已纳入的部分）

原因：
- 同名 skill 或相同输入在不同临时包版本下必须隔离缓存命中域。

### Decision 3: `no_cache` 仍为最高优先级禁用开关
即使在 `auto` 模式：
- 当 `runtime_options.no_cache=true` 时，系统必须跳过 cache lookup 和 write-back。

原因：
- 保持既有 API 契约与调试能力；
- 避免引入行为倒退。

### Decision 4: Repair-success 缓存语义与 auto-only 策略对齐
`repair-success 可缓存` 的要求解释为：
- 在缓存开启前提下（`auto` 且非 `no_cache`）可写入缓存；
- `interactive` 模式下即使 repair-success 也不写缓存。

原因：
- 消除规格间冲突；
- 保持规则单一来源：缓存门禁先于缓存写入条件。

### Decision 5: 常规与临时链路缓存存储物理隔离
缓存实现采用两张独立表：
- 常规链路缓存表（现有 `cache_entries`）
- 临时 skill 缓存表（新增 `temp_cache_entries`）

并在运行收敛时按链路写入：
- 常规 run 成功写入常规缓存表；
- 临时 run 成功写入临时缓存表。

原因：
- 即使 key 设计已包含临时包哈希，物理隔离仍可降低跨链路污染风险；
- 有利于后续链路独立运维（清理、统计、限额）。

## Risks / Trade-offs

- [风险] 临时包哈希计算口径不一致导致命中不稳定  
  → Mitigation: 以“原始上传压缩包字节流”作为哈希输入，不依赖解压顺序。

- [风险] 历史测试假设“临时链路永不缓存”导致回归失败  
  → Mitigation: 按模式重写断言，新增 auto/interactive 双场景覆盖。

- [风险] key 组成变化降低已有命中率  
  → Mitigation: 此变更仅扩展临时链路 key 维度，属于正确性优先。

## Migration Plan

1. 更新 `ephemeral-skill-upload-and-run` 规格：改写临时链路缓存要求与场景。
2. 更新 `mixed-input-protocol` 规格：显式声明 cache auto-only 门禁。
3. 更新 `output-json-repair` 规格：将 repair-success 缓存语义限定在缓存可用模式。
4. 实现层在临时链路引入 package hash 参与 key 计算，并接入 lookup/write-back。
5. 将临时链路缓存读写切换到独立缓存表，并在 orchestrator 中按链路写入对应缓存表。
6. 回归测试覆盖：
   - 临时链路：auto 命中、interactive 不命中、不同 zip 不同 key；
   - 常规链路：interactive 不写缓存守护不回退。
