# AutoSkill 包构建指南

本文说明什么是 AutoSkill 包、它与普通 Open Agent Skills 包的区别、在 Skill-Runner 中可执行所需规范，以及如何把普通 Skill 包转换为 AutoSkill 包。

## 1. 什么是 AutoSkill 包

### 1.1 定义

AutoSkill 包是“可被 Skill-Runner 稳定自动执行”的 Skill 包。  
它不仅包含 `SKILL.md` 的行为描述，还必须提供机器可校验的执行合同（输入、参数、输出、artifact 约束）。

### 1.2 与普通 Open Agent Skills 包的区别

普通 Skill（Open Agent Skills 语义）通常关注“给 Agent 的指令”，而 AutoSkill 还要求“可自动运行、可验证、可复现”。

核心差异：

- 普通 Skill：通常只要 `SKILL.md`（以及可选脚本/参考文件）即可交互式使用。
- AutoSkill：必须补齐 `assets/runner.json` 与 schema 合同，确保服务端可自动编排执行。
- 普通 Skill：允许大量临时决策和交互分支。
- AutoSkill：需要收敛输入输出边界，减少运行中临时决策，支持稳定自动化。
- 普通 Skill：输出格式可灵活。
- AutoSkill：输出必须满足 `output.schema.json`，artifact 必须可定位与校验。

## 2. AutoSkill 包需遵循的规范

### 2.1 目录结构（最小集）

```text
<skill_id>/
  SKILL.md
  assets/
    runner.json
    input.schema.json
    parameter.schema.json
    output.schema.json
```

建议附加：

```text
<skill_id>/
  references/
    ... 参考文档
  scripts/
    ... 可复用脚本（非必须）
```

### 2.2 身份一致性

以下三者必须一致，否则会被判为非法包：

- 顶层目录名：`<skill_id>`
- `assets/runner.json` 中 `id`
- `SKILL.md` frontmatter 中 `name`

### 2.3 runner.json 必填要点

`runner.json` 至少应包含：

- `id`
- `version`（建议单调递增，如 `1.0.0`）
- `engines`（非空列表）
- `schemas.input` / `schemas.parameter` / `schemas.output`
- `artifacts`（非空列表，描述产物模式）

说明：

- `engines` 是强约束，只允许列表中的引擎执行。
- `version` 建议采用数字点分形式（例如 `1.2.0`）。

### 2.4 输入/参数/输出协议

详细规则见 `docs/file_protocol.md`，这里给出关键约束：

- `input.schema.json`：定义业务输入；支持 `file`（上传文件路径）与 `inline`（请求体 JSON 值）两类来源。
- `parameter.schema.json`：定义标量配置参数（string/number/bool 等）。
- `output.schema.json`：定义结构化输出与 artifact 字段。

### Artifact 字段规范

在 `output.schema.json` 的属性里，对文件产物字段标记：

- `x-type: "artifact"`（必须）
- `x-role`（建议）
- `x-filename`（建议）

并确保 `required` 与实际可产出路径一致，避免“必填但不可生成”。

### 2.5 自动执行友好性要求

为保证在 Skill-Runner 中稳定运行，`SKILL.md` 应满足：

- 明确输入、参数、输出字段语义。
- 明确失败分支和返回格式。
- 尽量减少“执行中需要用户临时决策”的步骤；若必须决策，需参数化或约束化。
- 对最终输出 JSON 给出明确结构要求。

## 3. 如何构建 AutoSkill 包

推荐按以下顺序进行：

1. 明确任务类型  
   先判断是“直接返回结果 / 产出文件 / 修改文件”中的哪一类。

2. 收敛执行边界  
   写清楚输入来源、允许的参数、输出字段、失败条件。

3. 编写或 patch `SKILL.md`  
   将交互式模糊描述改为可自动执行的步骤，并显式要求返回结构化 JSON。

4. 编写三类 schema  
   - `input.schema.json`：定义业务输入（可混合 file 与 inline）
   - `parameter.schema.json`：只放配置参数
   - `output.schema.json`：放结构化输出与 artifact 定义

5. 编写 `runner.json`  
   声明 `engines`、schema 路径、artifact 合同、版本等。

6. 做本地校验  
   检查身份一致性、schema 文件存在性、字段 required 合理性、artifact 是否可实际产出。

7. 用小样本试跑  
   在最小输入下先跑通一次，确认输出 JSON 与 artifact 都符合 schema。

## 4. 如何从普通 Skill 包转换为 AutoSkill 包

### 4.1 转换思路

把“以人类交互为中心”的 Skill，转换为“以合同为中心”的 Skill。

转换时关注三件事：

- 能否稳定判断输入？
- 能否稳定约束输出？
- 能否定义可验证的产物？

### 4.2 实操步骤

1. 读取原始 Skill 包  
   重点看 `SKILL.md`、脚本依赖、引用文档。

2. 分类并评估可转换性  
   可使用三分类：
   - `not_convertible`
   - `convertible_with_constraints`
   - `ready_for_auto`

3. patch `SKILL.md`  
   - 删除/收敛不可自动化的临时决策点
   - 明确输入、参数、输出、失败处理
   - 明确最终 JSON 输出结构

4. 新增 `assets/*`  
   生成 `runner.json` 与三类 schema。

5. 补充参考文档  
   将实现相关规范（如 `file_protocol.md`）放入 `references/`，并在 `SKILL.md` 显式引用。

6. 校验与试跑  
   先做静态校验，再做一次真实执行，确认合同闭环。

### 4.3 常见问题与建议

- 问题：`SKILL.md` 中“让用户中途决定下一步”。  
  建议：改成参数化（`mode`、`strict` 等）或固定策略。

- 问题：输出字段很多，但 artifact 没有显式声明。  
  建议：在 `output.schema.json` 中为文件字段加 `x-type: "artifact"`。

- 问题：包身份不一致（目录名、runner id、frontmatter name 不同）。  
  建议：统一为同一个 `skill_id`。

- 问题：引擎声明缺失或为空。  
  建议：在 `runner.json.engines` 明确列出可执行引擎。

## 5. 最小检查清单（提交前）

- [ ] 顶层目录、`runner.id`、`SKILL.md` name 三者一致
- [ ] `SKILL.md`、`runner.json`、三类 schema 均存在
- [ ] `runner.json.engines` 非空
- [ ] `runner.json.schemas` 路径有效
- [ ] `runner.json.artifacts` 非空且与输出一致
- [ ] `output.schema.json` 对 artifact 字段已标注 `x-type: "artifact"`
- [ ] 必填字段可被真实执行路径产出
- [ ] 在目标引擎下完成至少一次试跑

---

参考：

- `docs/file_protocol.md`
- `docs/api_reference.md`
- `docs/run_artifacts.md`
