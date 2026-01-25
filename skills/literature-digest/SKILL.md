---
name: literature-digest
description: Generate a paper digest (Markdown) and extract reference entries (structured JSON array) from a MinerU-produced paper Markdown file. Use when invoked as $literature-digest with a prompt-embedded JSON payload containing md_path.
compatibility: Requires local filesystem read access to md_path; no network required.
---

# literature-digest（literature_digest_v1）

本 skill 运行于后台自动化场景：**不得向用户提问做决策**。遇到分支/不确定性时，必须按“默认行为协议”继续执行，并输出 schema 兼容 JSON。

stdout **只能**输出一个 JSON 对象（不得夹杂日志/解释文本）。

## 输入（prompt payload）

从 prompt 中读取：
- `md_path`：待解析的论文 Markdown 文件路径。
- `language`： 论文总结使用的语言。

约束：
- `md_path` 是唯一内容来源；以 UTF‑8 读取。
- `language` 示例：
  - `zh-CN`（默认）
  - `en-US`
  - ......
  无法识别 `language` 时，回退 `zh-CN`（只影响 `digest` 语言）。

## 输出（stdout JSON）

输出 JSON 必须包含（即使为空也要存在）：

- `digest_path`：输出文件路径（内容为 Markdown 纯文本；**不包含**插件侧协议头；协议头由插件端组装写入 Zotero note）
- `references_path`：输出文件路径（内容为 UTF‑8 JSON 数组）
- `provenance.generated_at`：UTC ISO‑8601
- `provenance.input_hash`：`sha256:<hex>`（对 `md_path` 文件 bytes 计算）
- `provenance.model`：解析使用的模型
- `warnings`：数组
- `error`：`object|null`

`references_path` 指向的 JSON 数组中，每条必须包含：
- `author: string[]`
- `title: string`
- `year: number|null`
- `raw: string`
- `confidence: number`（0~1）

可选扩展字段（尽量对齐 Zotero；缺失允许）：
- `DOI`（大写）
- `url`、`arxiv`
- `itemType`、`creators`、`date`
- `publicationTitle`、`volume`、`issue`、`pages`
- `publisher`、`place`、`ISBN`、`ISSN`

不输出字段：
- `citationKey`（由 Better BibTeX 负责）

## 处理步骤（建议工作流）

1) 解析 prompt，做最小校验与默认值回退。
2) 读取 `md_path`（UTF‑8）并计算 `input_hash`（sha256）。
3) 使用全文 Markdown 生成“结构化骨架”（建议为 JSON）：包含大纲与 references 区块位置（按原始 md 行号 1-based）。
4) 基于骨架：
   - 生成 digest（全局总结 + 分章节总结）
   - 定位 references 区块并抽取条目
5) 对输出做最小自检与修正（schema/类型/范围），确保可被严格 JSON 解析。
   - 推荐使用 `scripts/validate_output.py` 做格式验证与自动修复（见下文）。

## LLM 与脚本的职责边界（重要）

为避免某些 agent 在运行时“越界”导致质量下降，需强制遵守以下边界：

- **必须由 LLM 执行（不得用脚本替代）**：
  - 基于全文理解生成 digest（全局总结 + 分章节总结）
  - 基于全文理解生成结构化骨架（大纲、章节范围、references 区块定位）
  - 参考文献条目的语义级字段推断（作者/标题等）在规则不稳时的补全

- **允许用脚本执行（确定性/可重复）**：
  - 读取 `md_path`、计算 sha256、生成 `provenance`
  - 输出 schema 校验、字段迁移、类型纠正、将过长输出物化到文件（`digest_path`/`references_path`）

- **绝对禁止**：
  - 不得擅自创建新的 Python/JS/Bash 脚本去“替代 LLM 的摘要/大纲/语义判断工作”（即使看起来可自动化）。
  - 除本 skill 已提供的脚本（`scripts/provenance.py`、`scripts/validate_output.py`）外，不应新增脚本来完成上述 LLM 任务。

### Digest 输出结构（Markdown）

`language=zh-CN` 时：
- 必须严格使用如下标题（顺序与标题文本均固定）：
  - `## TL;DR`（建议 8~15 行；比之前更详尽，覆盖问题/方法/结果/局限与可复现性线索）
  - `## 研究问题与贡献`
  - `## 方法要点`
  - `## 关键结果`
  - `## 局限与可复现性线索`
  - `## 分章节总结`
- 不要输出额外的顶层标题（例如 `# 文献摘要`）或“论文信息/元数据”区块；论文题目、作者等信息不强制输出（避免格式漂移）。
- 全局总结（`## TL;DR` 到 `## 局限与可复现性线索`）的总输出量应显著增加：相较“精简版”约提升至约 3 倍信息量（更多要点、更多关键细节与限定条件，但仍避免臆造）。
- `## 分章节总结` 必须存在，并尽可能细化章节切分（根据提取出来的大纲）：
  - 优先按“全文大纲骨架”的章节标题逐章总结（推荐使用 `### <原文章节标题>`）
  - 章节粒度要求：尽量覆盖主要一级章节；若某一级章节过长或包含多个子主题，优先进一步拆成二级小节（`#### <子节标题或子主题>`）
  - 数量要求：至少输出 8 个章节/小节块（`###` 或 `####`），并尽量更多
  - 内容要求：分章节总结的总输出量应显著增加：相较“精简版”约提升至约 5 倍信息量（更细粒度、更具体的术语/变量/设置/结论/边界条件；必要时引用原文中的关键符号/损失项/模块名/数据集名，但不要贴长段原文）
  - 若无法可靠识别大纲：退化为 `### 片段 1/2/3...` 的分段总结，并将片段数量提升（至少 8 段），以覆盖全文主要内容

`language=en-US` 时：
- Must use the exact headings below (fixed order and text):
  - `## TL;DR` (prefer 8–15 lines; more detailed than a short summary)
  - `## Research Question & Contributions`
  - `## Method Highlights`
  - `## Key Results`
  - `## Limitations & Reproducibility`
  - `## Section-by-Section Summary`
- Do not add an extra top-level title (e.g. `# Paper Digest`) or a “Paper Info/Metadata” section.
- The overall “global summary” volume (from `## TL;DR` to `## Limitations & Reproducibility`) should be ~3× a short version: add more concrete details and qualifiers without hallucinating.
- `## Section-by-Section Summary` must exist and be as fine-grained as possible based on the extracted outline:
  - Prefer `### <Original section heading>` in outline order
  - If a section is long or covers multiple themes, split further into `#### <subtopic>` blocks
  - Output at least 8 section/subsection blocks (`###` or `####`) and preferably more
  - Make the section-by-section part ~5× a short version: more specifics (modules, losses, datasets, settings, claims, limits); avoid long verbatim quotes
  - Fallback to `### Segment 1/2/3...` with at least 8 segments if headings are unreliable

#### Digest 模版（建议直接填充，不要改标题）

`language=zh-CN` 模版：

```md
## TL;DR
（建议 8~15 行；更具体、更完整）

## 研究问题与贡献
- 
- 
- 

## 方法要点
- 
- 
- 

## 关键结果
- 
- 
- 

## 局限与可复现性线索
- 
- 
- 

## 分章节总结
### （章节1标题）
- 
- 
- 

### （章节2标题）
- 
- 
- 

### （章节3标题）
- 
- 
- 

### （章节4标题）
- 
- 
- 

### （章节5标题）
- 
- 
- 

### （章节6标题）
- 
- 
- 

### （章节7标题）
- 
- 
- 

### （章节8标题）
- 
- 
- 
```

`language=en-US` template:

```md
## TL;DR
(Prefer 8–15 lines; be more specific)

## Research Question & Contributions
- 
- 
- 

## Method Highlights
- 
- 
- 

## Key Results
- 
- 
- 

## Limitations & Reproducibility
- 
- 
- 

## Section-by-Section Summary
### (Section 1 heading)
- 
- 
- 

### (Section 2 heading)
- 
- 
- 

### (Section 3 heading)
- 
- 
- 

### (Section 4 heading)
- 
- 
- 

### (Section 5 heading)
- 
- 
- 

### (Section 6 heading)
- 
- 
- 

### (Section 7 heading)
- 
- 
- 

### (Section 8 heading)
- 
- 
- 
```

### References 抽取原则

- 无法定位 references 区块：`references=[]`（digest 可正常生成）
- 多个候选 references：默认选择“最后一个且长度合理”的区块
- 条目分割不稳定：保留 `raw`，并输出 `author=[]`、`title=""`、`year=null`，`confidence` 置低（例如 0.1）
- 关键标识优先提取：`DOI`、`url`、`arxiv`、`year`（可用正则/启发式；其余字段尽力）
- 在参考文献条目抽取中遇到体例识别、条目切分或字段边界问题时，可参考：`references/bibliography_formats.md`
- 作者字段抽取（非常重要，避免丢失名缩写）：
  - `author[]` 的目标是保留**可直接展示/匹配**的作者字符串；优先按 `raw` 中出现的形式保存（常见为 `Surname, Initials.` 或 `Initials. Surname`）。
  - 不要只输出姓（例如把 `Al-Rfou, R.` 简化为 `Al-Rfou`）；必须尽量保留 given name 的缩写/首字母（如 `R.`、`Q.V.`、`L.S.`）。
  - 对 `et al.` / `等`：仅表示作者被截断；可以将 `et al.` 作为作者列表中的最后一项（例如 `"et al."`），或写入 `warnings` 并降低 `confidence`，但不要擅自补全不存在的作者。
  - 例（期望输出）：
    - `raw`: `Bahdanau, D., Cho, K., Bengio, Y.: ...` → `author`: `["Bahdanau, D.", "Cho, K.", "Bengio, Y."]`
    - `raw`: `Bodla, N., ... Davis, L.S.: ...` → `author`: `["Bodla, N.", "...", "Davis, L.S."]`
    - `raw`: `Le, Q.V.: ...` → `author`: `["Le, Q.V."]`（注意不要拆丢 `Q.V.`）

## 默认行为协议（必须遵守）

- 读取 `md_path` 失败（不存在/无权限/编码异常）：
  - 输出 schema 兼容 JSON
  - `digest_path=""`
  - `references_path=""`
  - `error` 填充 `{code,message}`
- `language` 非支持值：回退 `zh-CN` 并写入 `warnings`
- 任何字段抽取不可靠时：宁可留空 + 降低置信度，也不要臆造

## 脚本（可选但推荐）

本 skill 允许使用脚本承担确定性工作（审计信息生成、输出格式验证、自我修复），以降低 LLM 负担并提高一致性。

### `scripts/provenance.py`

用途：
- 计算 `provenance.input_hash`（对 `md_path` 文件 bytes 的 `sha256:<hex>`）
- 生成 `provenance.generated_at`（UTC ISO‑8601）

### `scripts/validate_output.py`

用途：
- 校验输出是否满足 schema（字段存在、类型正确、范围正确）
- 在校验失败时做“可解释的自动修复”（例如补齐缺失字段、类型纠正、旧字段迁移、将过长输出物化到文件），并将修复记录写入 `warnings`

建议用法：
1) 先生成一个候选输出 JSON（可能不完美）
2) 使用 `scripts/validate_output.py --mode fix --md-path <md_path>` 输出修复后的 JSON
3) 再用 `scripts/validate_output.py --mode check` 校验必须通过；若仍失败，回退到最小可用输出（空 digest/空 references + error）

输出物化（避免 stdout 截断）：
- 为避免 stdout 截断，必须将结果文件直接写入**输入文档 `md_path` 所在目录**（便于受限 agent 访问）：
  - `digest_path=<dir_of_md_path>/digest.md`
  - `references_path=<dir_of_md_path>/references.json`
- 文件名固定：`digest.md` 与 `references.json`（UTF‑8）。
