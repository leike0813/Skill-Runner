# Open Agent Skills 规范速览与开发指南

本文用于在本仓库内快速理解 **Open Agent Skills（Agent Skills）** 的格式规范，并给出一套可操作的 **agent skill** 开发流程与检查清单。

> 参考来源（缓存于本仓库）：`artifacts/agentskills_specification_clean.txt`（由 `https://agentskills.io/specification` 抓取整理）

---

## 1. Agent Skill 是什么

**Skill** 可以理解为“可复用的任务说明书 +（可选）脚本/模板/参考资料”的目录包。Agent 在识别到任务匹配某个 skill 后，会加载该 skill 的 `SKILL.md` 并按其中步骤执行；当需要更多细节时，再按需读取 `references/`、`assets/`，或运行 `scripts/`。

核心目标：
- 可发现：通过 `name/description` 让 agent 更容易选中该 skill
- 可执行：步骤清晰、输入输出明确、失败模式可处理
- 可扩展：长文拆分到 `references/`，工具/代码放入 `scripts/`
- 可验证：能用工具校验结构与 frontmatter 合规

---

## 2. 目录结构规范（最低要求）

一个 skill 本质上是一个目录，至少包含：

```
skill-name/
└── SKILL.md          # 必需
```

可选目录（按需使用）：
- `scripts/`：可执行脚本（Python/Bash/JS 等，取决于运行环境）
- `references/`：按需加载的补充说明（小而聚焦）
- `assets/`：静态资源（模板、示例数据、查表文件等）

---

## 3. `SKILL.md` 格式与字段约束

`SKILL.md` 必须是：
- **YAML frontmatter**（以 `---` 包裹）+ **Markdown 正文**

### 3.1 必填字段

**`name`（必填）**
- 1–64 字符
- 仅允许：小写字母/数字/连字符（`a-z0-9-`）
- 不能以 `-` 开头或结尾
- 不能包含连续 `--`
- 必须与父目录名一致

**`description`（必填）**
- 1–1024 字符
- 需要同时描述：
  - 这个 skill 做什么
  - 什么时候应该用它（包含关键词）

最小示例：

```yaml
---
name: skill-name
description: A description of what this skill does and when to use it.
---
```

### 3.2 可选字段

`license`（可选）
- 建议简短：许可证名或指向随包文件（如 `LICENSE.txt`）

`compatibility`（可选）
- 1–500 字符
- 用于声明环境要求（依赖工具、网络需求、运行产品等）

`metadata`（可选）
- 字符串到字符串的键值映射（自定义扩展元数据，如 author/version）

`allowed-tools`（可选，实验性）
- 空格分隔的“预批准工具”列表（支持程度因 agent 实现而异）

示例（含可选字段）：

```yaml
---
name: pdf-processing
description: Extract text and tables from PDF files, fill forms, merge documents.
license: Apache-2.0
compatibility: Requires git, docker, jq, and access to the internet
metadata:
  author: example-org
  version: "1.0"
allowed-tools: Bash(git:*) Bash(jq:*) Read
---
```

---

## 4. 编写原则：Progressive Disclosure（渐进式披露）

规范建议按“由浅入深”组织内容，降低上下文消耗：
- **Metadata**：`name/description` 会被广泛用于发现与匹配（应精准）
- **Instructions**：`SKILL.md` 正文建议控制在 **5000 tokens** 左右，且尽量 **< 500 行**
- **Resources**：复杂细节拆到 `references/`，脚本放到 `scripts/`，模板放到 `assets/`

---

## 5. 文件引用约定

在 `SKILL.md` 中引用其他文件时：
- 使用 **skill 根目录的相对路径**，例如：
  - `references/REFERENCE.md`
  - `scripts/extract.py`
- 避免深层级“引用链”（建议从 `SKILL.md` 出发最多“一级跳转”）

---

## 6. 校验（Validation）

规范建议使用 `skills-ref` 工具进行格式校验：

```bash
skills-ref validate ./my-skill
```

它会检查：
- `SKILL.md` frontmatter 是否有效
- `name/description` 是否符合约束
- 目录结构是否符合规范

---

## 7. 如何开发一个 Agent Skill（可操作流程）

下面是一套从 0 到可发布的流程（适用于多数工程型 skill）：

### Step 0：明确“任务边界/验收标准”

写清楚：
- 输入是什么（路径/格式/编码/是否允许网络）
- 输出是什么（文件路径/字段/可追溯性）
- 不做什么（边界：不改源文件、不写回外部系统等）
- 失败时如何表现（可读错误、空输出、warnings）

### Step 1：确定 `name` 与目录名

- 目录名即 skill 名（必须一致）
- 使用清晰、可检索的词：例如 `literature-match`、`pdf-processing`

### Step 2：编写 `SKILL.md`（先写“说明书”，再写代码）

建议正文结构（不是强制）：
- What this skill is（用途与触发关键词）
- Invariants / boundaries（强约束）
- Interfaces（输入/输出/中间产物）
- Step-by-step（按顺序可执行）
- Failure modes（失败场景与行为）
- Local fixtures（本地小样例）

**关键点**：在正文中把“agent 需要做的决策”显式写出来（而不是只写代码实现）。

### Step 3：把“可重复/可校验”的部分脚本化（`scripts/`）

适合脚本化的通常包括：
- 纯确定性处理（解析/归一化/索引/格式化）
- 可重复运行、幂等的产物生成
- 结构化输出落盘（避免对话输出截断）

脚本要求（建议）：
- 自包含或明确依赖
- 错误信息可读（指明缺失的输入/字段/环境）
- 对缺失字段有容忍度（避免崩溃）

### Step 4：将“长说明/领域知识/格式模板”放到 `references/`

适用场景：
- 复杂的 schema 说明
- 特定领域规则（例如引用格式/法律条款/金融字段定义）
- 多个变体流程的对比与选型说明

### Step 5：准备可复现的小样例（fixtures）

推荐在仓库内提供：
- 小输入（可脱敏）
- 对应的稳定输出
- 让开发者与 agent 都能快速跑通

### Step 6：验证与迭代

- `skills-ref validate`：验证规范合规
- 在目标运行环境中执行关键脚本（确保依赖与路径正确）
- 用最小样例做 E2E 跑通（并记录命令）

### Step 7：发布（打包 skill 目录）

发布时通常只需要：
- `SKILL.md`
- `scripts/`（运行时需要的脚本）
- `assets/`（运行时需要的静态资源）
- `references/`（运行时需要的补充说明；不需要的可移出发布包）

---

## 8. 开发者检查清单（Checklist）

- `SKILL.md` 存在，且 YAML frontmatter 合法
- `name` 与目录名一致，且符合字符约束
- `description` 足够具体（含“何时使用”关键词）
- `SKILL.md` 步骤可执行，输入输出与落盘路径明确
- 长文已拆分到 `references/`（避免 `SKILL.md` 过长）
- `scripts/` 脚本可在目标环境运行、错误信息可读
- 有最小样例可验证（fixtures / artifacts）
- `skills-ref validate` 通过

