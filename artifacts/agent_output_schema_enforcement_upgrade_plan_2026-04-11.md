# Agent 结构化输出强化改造方案

日期：2026-04-11

## 1. 背景与现状问题

当前 skill 执行链路在“输出收敛”这一层仍以弱约束为主，主要表现为：

1. prompt 注入只提供软提示，不能保证 agent 严格返回结构化数据。
2. 最终输出依赖末端兜底修复，说明系统默认接受 agent 输出不稳定这一事实。
3. `interactive` 模式靠 `__SKILL_DONE__` 判断结束，但该标志本身仍然是 prompt 约束，不是协议强约束。
4. `interactive` 的中间轮次通过 `<ASK_USER_YAML>` 形成 UI hint，这是一套与最终 JSON 输出并行存在的弱协议。
5. `auto` 与 `interactive` 的输出语义分裂，导致编排器、审计、测试、前端消费都存在额外分支。

这套机制在模型能力强、patch 设计好的情况下尚可工作，但对较弱模型、较弱 agent 或复杂 skill 来说，输出不稳定会成为系统性问题。当前问题不是单点 bug，而是协议层没有把“输出必须结构化”提升为真正的运行时合同。

本次升级的目标不是先做局部修补，而是将“所有输出统一进入结构化 JSON 合同”作为核心方向，并据此规划后续实现。

## 2. 改造目标与最终合同

### 2.1 总体目标

1. 无论 `auto` 还是 `interactive`，agent 输出都必须是 JSON 对象。
2. 编排器对每轮输出做 schema 校验；校验失败时生成 repair prompt 回灌给 agent，最多重试 `n` 次。
3. `auto` 和 `interactive` 使用统一的结构化输出治理框架，只在目标 schema 上区分。
4. 不再保留 `<ASK_USER_YAML>`、fenced ask-user block、或其他自由文本提示协议。
5. 对支持原生 schema 约束的 engine，在调用阶段就下发 schema，再叠加编排器外层校验与重试。

### 2.2 核心设计决策

本次方案固定以下决策，不留给后续实现者再做判断：

1. `interactive` 不能预先知道某一轮输出是“中间态”还是“最终态”，因此不能拆成两套独立入口 schema。
2. `interactive` 必须使用一个联合 schema，在同一对象合同内同时接受中间态和终态。
3. schema repair retries 属于单一 attempt 内的内部轮次，不改变 `attempt_number`。
4. 若超过 `n` 次仍不满足 schema，不直接短路到 `failed`，而是回落到现有后续逻辑。
5. `<ASK_USER_YAML>` 兼容明确废弃，后续实现中整体删除，不做保留期。

## 3. 输出协议设计

### 3.1 `auto` 模式输出合同

`auto` 模式只接受最终输出合同。目标 JSON 对象结构为：

```json
{
  "__SKILL_DONE__": true,
  "...": "其余字段满足当前 skill 的 output.schema.json"
}
```

运行时要求：

1. `__SKILL_DONE__` 必须存在且必须为 `true`。
2. 去掉 `__SKILL_DONE__` 后，其余字段必须满足 skill 当前的 `output.schema.json`。
3. 不接受“结构上像 ask_user”但 `__SKILL_DONE__ = false` 的中间态对象。

### 3.2 `interactive` 模式联合 schema

`interactive` 使用联合 schema。它本质上是一个 `oneOf` 合同，包含两个分支。

#### 分支 A：最终输出

```json
{
  "__SKILL_DONE__": true,
  "...": "其余字段满足当前 skill 的 output.schema.json"
}
```

要求：

1. `__SKILL_DONE__` 必须存在且为 `true`。
2. 去掉 `__SKILL_DONE__` 后，其余字段必须满足 skill 的 `output.schema.json`。
3. 不允许再混入 `message/ui_hints` 这类中间态专用字段，除非业务 schema 本身声明了这些字段。

#### 分支 B：非最终输出

```json
{
  "__SKILL_DONE__": false,
  "message": "agent 要询问用户的正文",
  "ui_hints": {}
}
```

要求：

1. `__SKILL_DONE__` 必须存在且为 `false`。
2. `message` 必须为非空字符串。
3. `ui_hints` 必须为对象。
4. `ui_hints` 的作用和语义沿用当前 ask-user hint 体系，但承载方式变成 JSON 对象字段。
5. 非最终输出不再允许通过自由文本、YAML tag、或 fenced block 表达用户交互意图。

### 3.3 `ui_hints` 的合同边界

后续实现时，`ui_hints` 应与当前 `ask_user.schema.yaml` 的能力域对齐，但不要求完全沿用旧文件的序列化形状。新合同以“前端可直接消费、编排器可稳定投影到 `PendingInteraction`”为目标。

建议保留的语义能力：

1. `kind`
2. `prompt`
3. `hint`
4. `options`
5. `files`
6. 额外展示提示字段

但新的主合同应放在 runtime 与 interactive 输出协议层，而不是继续依赖 `<ASK_USER_YAML>` 的独立注入模板。

## 4. 编排器校验、重试与审计设计

### 4.1 统一处理流程

每轮 agent 输出后，编排器必须按以下固定顺序处理：

1. 提取 JSON 对象候选。
2. 根据 execution mode 选择目标 schema：
   - `auto`：最终输出 schema
   - `interactive`：联合 schema
3. 做 JSON schema 校验。
4. 若校验失败，则构造 repair prompt。
5. 将 repair prompt 回灌给 agent，进入下一轮内部修复。
6. 最多重试 `n` 次，默认 3 次。
7. 若仍不满足 schema，则退出 repair loop，并回到现有结果归一化后续逻辑。

### 4.2 repair loop 语义

repair loop 的设计边界如下：

1. repair rounds 属于同一 attempt 内部行为。
2. repair 不创建新的 run attempt，不写新的 attempt 分隔。
3. repair 不应抢先产生 `waiting_user`，除非某轮输出已经是合法的 `interactive` 中间态 JSON。
4. repair 失败后不得直接强行判 `failed`；仍需交由现有 lifecycle 决策器处理。

### 4.3 repair prompt 生成规则

repair prompt 必须基于 schema 校验错误自动生成，不能继续依赖手写的自由提示。后续实现应至少包含：

1. 当前期望的 schema 摘要
2. 校验失败字段与路径
3. 一个最小合法 JSON 例子
4. 强约束提示：仅返回 JSON 对象，不输出解释、Markdown、YAML、代码块

对于 `interactive` 模式，repair prompt 还需要强调：

1. 如果任务已完成，则输出 `__SKILL_DONE__ = true` 的最终对象
2. 如果需要用户输入，则输出 `__SKILL_DONE__ = false` 的中间态对象

### 4.4 审计与运行时事件

后续实现时，审计数据必须显式记录 repair 过程，而不是只留下最终结果。建议新增或统一记录：

1. 原始 agent 输出
2. JSON 提取结果
3. schema 校验错误列表
4. repair round index
5. repair prompt 本体或其摘要
6. repair 后的新输出
7. 是否收敛成功
8. 若未收敛，最终回落到的后续判定路径

这一层不一定新增对外 FCMP 事件，但至少要在内部审计与 orchestrator event 中有稳定痕迹。

## 5. Engine 接入设计

### 5.1 总体原则

原生 schema 约束是前置 guard，不是真源。最终真源仍然是 Skill Runner 编排器的外层 JSON 提取、schema 校验与 repair loop。

实现时必须遵守：

1. engine 原生约束与外层校验同时存在
2. schema artifact 统一 materialize 到 run 目录
3. 不直接在命令行拼超长 schema JSON

### 5.2 Claude

Claude headless 调用层使用：

1. `--output-format json`
2. `--json-schema <schema>`

后续实现要求：

1. 将最终输出 schema 或 interactive 联合 schema materialize 到 run 目录
2. Claude command builder 根据当前模式注入对应 schema
3. resume 场景与 start 场景保持一致
4. 不让 UI shell 与 headless run 各自维护不同的结构化输出逻辑

### 5.3 Codex

Codex 调用层使用：

1. `--output-schema <FILE>`

后续实现要求：

1. 仍由统一 schema materialization 流程生成 schema file
2. command builder 在 start/resume 路径都注入该文件
3. 不把 schema 逻辑散落到 prompt patch 或 engine-specific hack 中

### 5.4 其他 engine

Gemini、iFlow、OpenCode、Qwen 本轮不要求原生 schema 约束，但后续实现应预留统一抽象，确保它们仍可复用外层 JSON/schema repair 主链，不出现第二套结构化输出协议。

## 6. 对现有协议与系统的影响

### 6.1 `ask_user.schema.yaml`

该文件后续不再用于生成 `<ASK_USER_YAML>` 注入模板，而应被重新定位为：

1. `interactive` 中间态 JSON 的 `ui_hints` 能力约束来源之一
2. 或作为新 interactive output branch schema 的拆分子定义

不允许继续把它当成独立于主输出协议之外的“辅助 YAML 合同”。

### 6.2 `PendingInteraction`

前端和 API 的 `PendingInteraction` 不要求在本次改造中改变外部形状，但生成来源会变化：

1. 旧来源：ASK_USER_YAML / 推断 / 自由文本启发式
2. 新来源：合法的 `interactive` 中间态 JSON

后续实现要把 `interactive` 中间态 JSON 稳定投影成 `PendingInteraction`，逐步移除启发式推断。

### 6.3 软完成逻辑

当前 `interactive` 存在“无 marker + 有结构化输出 + schema 有效”的 soft completion 语义。改造后：

1. 如果是最终输出，要求显式 `__SKILL_DONE__ = true`
2. 中间态要求显式 `__SKILL_DONE__ = false`

因此后续实现应逐步收紧 soft completion，最终不再依赖“缺失 done marker 的猜测性完成”。本次文档把这一点定为目标方向。

### 6.4 `<ASK_USER_YAML>` 删除

后续实现中需要整体删除：

1. skill patch 中关于 ASK_USER_YAML 的注入合同
2. runtime stream 中对 `<ASK_USER_YAML>` / fenced ask-user block 的提取逻辑
3. 文档中所有将 ASK_USER_YAML 视为合法协议的描述

这一删除是明确目标，不保留兼容。

## 7. 分阶段实施计划

### 阶段 0：SSOT 与方案落盘

目标：

1. 先修改主规格、文档、schema 合同口径
2. 明确 `interactive` 联合 schema 和 JSON-only 方向

需要更新的对象：

1. `ask_user.schema.yaml`
2. interactive lifecycle / decision policy / engine turn protocol 主 specs
3. API reference
4. statechart / sequence 文档
5. output schema generation 指南

完成标准：

1. 仓库主 SSOT 不再承认 ASK_USER_YAML 是正式输出协议
2. 主文档明确 `interactive` 采用联合 schema

### 阶段 1：统一 schema 构造与 materialization

目标：

1. 新增统一的 runtime output schema builder
2. 能根据 execution mode 生成：
   - auto final schema
   - interactive union schema
3. 将 schema artifact materialize 到 run 目录

实施重点：

1. 不把 schema 拼装逻辑分散在 patcher、adapter、orchestrator 多处
2. schema builder 必须是唯一真源

完成标准：

1. 每个 run 都能得到可审计的目标输出 schema artifact
2. Claude/Codex 都能消费同一来源的 schema 文件或 schema 文档

### 阶段 2：engine 原生 schema 约束接入

目标：

1. Claude 接 `--json-schema`
2. Codex 接 `--output-schema <FILE>`

实施重点：

1. start / resume 路径一致
2. 不影响现有 auth、session handle、config compose 主链

完成标准：

1. CLI 实际启动参数可审计
2. 对应 adapter 测试能稳定断言 schema 参数已传入

### 阶段 3：编排器外层校验与 repair loop

目标：

1. 将现有零散的 JSON 提取、schema 校验、soft completion 判定整合为统一 repair loop
2. 对 auto / interactive 使用同一主流程

实施重点：

1. 默认 `n=3`
2. repair rounds 不增加 attempt
3. repair loop 结束后继续走现有后续逻辑，而不是直接失败

完成标准：

1. 非法 JSON 输出可被稳定修复或稳定回落
2. 审计中可完整看到 repair 过程

### 阶段 4：interactive 中间态 JSON 投影与旧逻辑删除

目标：

1. 将合法的中间态 JSON 作为 `PendingInteraction` 的主来源
2. 删除 ASK_USER_YAML 提取和自由文本 ask-user 启发式主路径

实施重点：

1. 前端/API 形状不乱改
2. waiting_user 语义不改变
3. 只替换“数据来源”

完成标准：

1. `interactive` 不再依赖 YAML tag
2. waiting_user 仍按现有协议正常工作

### 阶段 5：收紧完成判定与清理遗留逻辑

目标：

1. 逐步移除对“无 `__SKILL_DONE__` 但结构化输出有效”的软完成依赖
2. 清理所有已经不需要的 legacy 分支

完成标准：

1. 最终输出必须显式 `__SKILL_DONE__ = true`
2. 中间态必须显式 `__SKILL_DONE__ = false`
3. 历史兼容逻辑清理完成

## 8. 需要修改的主要区域

后续实现预计会涉及以下类型的区域：

### 8.1 协议与 schema

1. runtime contract schema
2. ask-user / pending-interaction 相关 schema
3. skill output schema patch 生成逻辑

### 8.2 编排器

1. run lifecycle
2. interaction lifecycle
3. schema validator
4. audit / orchestrator event

### 8.3 engine adapter

1. Claude command builder
2. Codex command builder
3. 统一 schema materialization 接口

### 8.4 文档与主 specs

1. interactive engine turn protocol
2. interactive run lifecycle
3. interactive decision policy
4. interactive job API
5. API reference
6. statechart / sequence

## 9. 测试与验收标准

### 9.1 联合 schema 测试

必须覆盖：

1. `interactive` 最终输出分支通过
2. `interactive` 中间态分支通过
3. 缺失 `__SKILL_DONE__` 拒绝
4. `__SKILL_DONE__ = false` 但缺 `message/ui_hints` 拒绝
5. `__SKILL_DONE__ = true` 但不满足 output.schema.json 拒绝

### 9.2 repair loop 测试

必须覆盖：

1. 第 1 轮即通过
2. 第 2 或第 3 轮修复通过
3. 超过 `n` 次仍失败但不直接短路
4. repair round 不增加 attempt_number

### 9.3 engine 接入测试

必须覆盖：

1. Claude 启动参数包含 `--json-schema`
2. Codex 启动参数包含 `--output-schema`
3. schema 文件或 schema artifact 正确 materialize 到 run 目录
4. start/resume 都使用同一 schema 来源

### 9.4 waiting_user / pending interaction 回归

必须覆盖：

1. 合法的 interactive 中间态 JSON 正确进入 `waiting_user`
2. `PendingInteraction` 投影稳定
3. interaction reply / resume 主链不回归
4. 不再依赖 `<ASK_USER_YAML>` 触发主路径

### 9.5 runtime 必跑套件

后续实现必须跑：

```bash
conda run --no-capture-output -n DataProcessing python -u -m pytest \
  tests/unit/test_session_invariant_contract.py \
  tests/unit/test_session_state_model_properties.py \
  tests/unit/test_fcmp_mapping_properties.py \
  tests/unit/test_protocol_state_alignment.py \
  tests/unit/test_protocol_schema_registry.py \
  tests/unit/test_runtime_event_protocol.py \
  tests/unit/test_run_observability.py
```

如果涉及交互去重、history 或 replay，再追加相关测试集。

## 10. 风险与回滚策略

### 10.1 主要风险

1. `interactive` 联合 schema 设计不当，可能导致中间态与终态歧义。
2. engine 原生 schema 约束可能与 prompt patch、CLI 输出格式、stream parser 行为产生耦合问题。
3. 删除 `<ASK_USER_YAML>` 后，旧 skill 或旧 prompt 可能立即失效。
4. 若 repair loop 与当前 lifecycle 判断混合不清，可能引入 waiting_user / completed / failed 的状态回归。

### 10.2 风险控制

1. 先改 SSOT，再改实现。
2. 先完成 schema materialization 和审计，再接 engine 参数。
3. 在删除 legacy ASK_USER_YAML 主链前，先确保 interactive 中间态 JSON 投影完整可用。
4. 将 repair loop 设计为可配置开关，便于早期灰度。

### 10.3 回滚策略

如果某阶段上线后出现大面积回归，应优先按层回滚：

1. 先关闭 engine 原生 schema 约束
2. 再关闭 repair loop，仅保留外层校验
3. 如仍不稳定，再回退到原有输出路径

但回滚不应恢复 `<ASK_USER_YAML>` 为长期主协议，只能作为紧急临时措施。

## 11. 本文档的实施约束

本文档是后续实现阶段的唯一施工蓝图。后续实现者应遵守：

1. 不再把 `<ASK_USER_YAML>` 当成正式协议。
2. 不再为 `interactive` 中间态和终态建立两个完全独立的入口校验链。
3. 不把 schema repair 做成 attempt 级重试。
4. 不把 engine 原生 schema 约束当成最终真源。
5. 不允许在未同步 SSOT 的情况下直接修改编排器代码。

