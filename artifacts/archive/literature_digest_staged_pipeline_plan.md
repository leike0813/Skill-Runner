# `literature-digest` 分阶段产出改造方案

## 摘要

- 保持对外契约不变：最终仍只输出 `digest_path`、`references_path`、`citation_analysis_path`，不改 HTTP API，不改 output schema。
- 问题定位为：`literature-digest` 在 `digest.md` 之后进入长静默语义处理阶段，尤其是 `references` 和 `citation_analysis`，容易触发下游约 300 秒的 SSE idle timeout。
- 方案是在 skill 内部引入“隐藏中间产物 + 多回合小批次处理 + 原子提升最终产物”，把大任务拆成多个短阶段，避免单次长静默。

## 关键实现变更

### 1. 只在 skill 层拆分，不改运行时协议

- 不修改 `server/runtime/*`，不新增 engine 级 timeout 逻辑，先在 `literature-digest` skill 内收敛问题。
- 保持最终 artifact 名称与路径语义不变：
  - `digest.md`
  - `references.json`
  - `citation_analysis.json`
- 保持当前严格失败语义：
  - 任一关键阶段失败，任务最终仍为 `failed`
  - 已成功生成的中间/最终文件可以保留用于诊断
  - 但不把未完成的 `references.json` / `citation_analysis.json` 作为成功结果发布

### 2. 引入隐藏阶段产物与原子发布

- 所有阶段中间结果写入 `.<cwd>/.literature_digest_tmp/`，不进入公开 artifacts。
- `digest.md` 继续可直接生成；`references.json` 与 `citation_analysis.json` 改为“先写 tmp，后原子提升”：
  - 只有全部分片合并、校验通过后，才写入最终 `artifacts/references.json`
  - 只有全部 citation 分析合并、校验通过后，才写入最终 `artifacts/citation_analysis.json`
- 新增或约定的隐藏中间文件：
  - `outline.json`
  - `references_scope.json`
  - `references.parts/part-*.json`
  - `references_merged.json`
  - `citation_scope.json`
  - `citation_preprocess.json`
  - `citation.parts/part-*.json`
  - `citation_merged.json`
  - `citation_report.md`

### 3. `references` 改为“小批次抽取 + 确定性合并”

- 在 `SKILL.md` 和 runner prompt 中明确改成以下顺序：
  1. 先基于 `source.md` 生成 `outline.json`，同时确定 references 区块
  2. 将 references 区块按“条目批次”切分，不按字符数切
  3. 每批只抽取固定上限的参考文献条目，写一个 `references.parts/part-XXX.json`
  4. 每写完一批立即落盘，不允许把全部 references 一次性在单轮里生成
  5. 最后用确定性 merge/normalize 生成 `references_merged.json`，校验通过后再发布为 `references.json`
- 批次规则固定，避免实现时再做决策：
  - 优先按已识别条目切分
  - 每批最多 `15` 条 reference
  - 若单条 reference 极长，允许单条独占一批
  - 合并时保持原文顺序，不重新排序
- 每个分片产物只允许包含该批的 JSON 数组，不允许混入全文结果。

### 4. `citation_analysis` 改为“三段式”

- 固定拆成三个阶段：
  1. `citation_scope` 决策
     - LLM 只负责输出 `citation_scope.json`
     - 不在这一轮同时生成最终 `citation_analysis`
  2. `citation semantics` 分批分析
     - 运行现有 `citation_preprocess.py` 生成 `citation_preprocess.json`
     - 以 `ref_index` 聚合后的 item 为单位切分批次
     - 每批最多 `12` 个引用条目，或最多 `30` 个 mentions`，先命中者为准
     - 每批只输出该批对应的 `items[]` 和 `unmapped_mentions[]`，写入 `citation.parts/part-XXX.json`
  3. `report_md` 汇总
     - 在已有 `citation_merged.json` 基础上，单独做一轮较短的 `report_md` 生成
     - 若这一步失败，则整个 `citation_analysis` 仍视为失败，不发布最终文件
- 最终 `citation_analysis.json` 由确定性 merge 组装：
  - `meta.scope` 取 `citation_scope.json`
  - `items` 来自所有 part 合并
  - `unmapped_mentions` 来自所有 part 合并
  - `report_md` 来自最终汇总阶段
- 合并时必须做这几项校验：
  - `mention_id` 全局唯一
  - 同一 `ref_index` 只能有一个最终 item
  - `items[].mentions + unmapped_mentions` 的 mention 总数必须和 `citation_preprocess.json` 一致
  - 不一致直接失败，不做“猜测修复”

### 5. 提示词、脚本与文档同步

- 更新 `skills_builtin/literature-digest/SKILL.md`
  - 明确禁止一次性生成完整 `references.json` / `citation_analysis.json`
  - 明确阶段文件、批次规则、原子发布和失败语义
- 更新 `skills_builtin/literature-digest/assets/runner.json`
  - 把 prompt 改成阶段式要求，而不是“一次性生成三大产物”
- 扩展 `skills_builtin/literature-digest/scripts/validate_output.py`
  - 支持对 merge 后的 `references` / `citation_analysis` 做最终校验
  - 失败时输出明确的 stage 级错误信息
- 需要新增确定性 helper scripts，用于：
  - references 分片切分与合并
  - citation parts 合并与覆盖校验
- 更新 `docs/skills/literature-digest.md`
  - 说明内部改为 staged pipeline
  - 说明对外结果契约不变

## 接口与类型影响

- 无公共 HTTP API 变更。
- `literature-digest` 的 `output.schema.json` 不变。
- 新增的仅是 skill 内部隐藏阶段文件，不属于公开接口。
- 最终失败时，`error.code` 应带阶段信息，至少区分：
  - `references_stage_failed`
  - `references_merge_failed`
  - `citation_scope_failed`
  - `citation_semantics_failed`
  - `citation_report_failed`
  - `citation_merge_failed`

## 测试计划

- 单元测试
  - references 分片切分：长 references 区块能稳定切成多批，顺序不变
  - references 合并：多个 `part-*.json` 合并后 schema 合法，顺序与批次无关
  - citation merge：mention coverage、`mention_id` 唯一性、`ref_index` 去重都能校验
  - 原子发布：part 成功但 merge 失败时，不生成最终 `references.json` / `citation_analysis.json`
- 集成测试
  - 现有 `literature-digest` full paper case 继续成功
  - 断言最终产物至少包含：
    - `digest.md`
    - `references.json`
    - `citation_analysis.json`
  - 增加一个“大 references + citation”样例，验证拆分链路被触发
- 回归场景
  - digest 成功、references 中途失败：任务 `failed`，`digest.md` 可保留，最终 `references.json` 不发布
  - references 成功、citation semantics 中途失败：任务 `failed`，最终 `citation_analysis.json` 不发布
  - 全流程成功：对外结果结构与当前兼容

## 假设与默认

- 默认采用“隐藏临时产物”，不公开新增 artifacts。
- 默认采用“严格失败”，不引入 partial success。
- 默认不修改运行时/引擎超时机制，先用 skill 内部阶段化拆分解决。
- 默认把问题重点收敛在 `references` 与 `citation_analysis`，`digest` 仅保持现状并作为已验证可工作的前置阶段。
