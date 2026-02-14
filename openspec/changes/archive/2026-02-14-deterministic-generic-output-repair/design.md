## Context

本变更是输出解析层的稳健性增强，不改变技能业务逻辑，不引入 LLM 二次修复，不引入脚本 fallback。

边界：

- 只做 deterministic generic repair；
- success 仍以 `output.schema` 通过为唯一标准；
- repair 只影响“解析前后处理”，不补业务字段语义。

## Decisions

### 1) 统一解析与修复管线

在适配器输出解析链中增加统一 deterministic 修复步骤：

1. 原始文本尝试 JSON 解析；
2. 若失败，尝试 envelope（如 `{"response":"..."}`）提取；
3. 对候选文本执行：
   - code fence 剥离；
   - 首尾空白清理；
   - first-json-object 提取；
4. 将解析结果交给 `output.schema` 校验。

该流程只做语法层/结构层修复，不进行语义补全。

### 2) 成功标准不变（Schema-first）

- repair 后必须通过 `output.schema` 才能标记 success；
- repair 后仍不通过时，保持 failed。

### 3) 可观测性与缓存

- repair-success 在 result 中新增 `repair_level`：
  - `none`（默认，无修复）
  - `deterministic_generic`（本次修复后成功）
- 同时记录 warning（例如 `OUTPUT_REPAIRED_GENERIC`）。
- repair-success 允许写入 cache（因已通过 schema，视为契约成功结果）。

## Non-Goals

- 不实现 skill-specific repair；
- 不实现脚本 fallback；
- 不实现基于 artifacts 的语义推断补全。

## Test Strategy

- 增加解析修复单测：
  - code fence + JSON
  - envelope.response + JSON
  - first-json-object 提取
- 增加 orchestrator 单测：
  - repair-success -> status=success、warning 存在、repair_level 正确、可入 cache
  - repair-failed -> status=failed

## Examples

以下示例用于明确“何时修复、如何修复、修复后如何判定”。

### 示例 1：Code Fence 包裹 JSON

**原始输出（stdout 关键片段）**

```text
任务已完成。
```json
{"digest_path":".../artifacts/digest.md","references_path":".../artifacts/references.json","provenance":{"generated_at":"2026-02-14T00:00:00Z","input_hash":"sha256:...","model":"gemini-3-pro-preview"},"warnings":[],"error":null}
```
```

**修复动作**
- 剥离 code fence；
- 提取 JSON 字符串；
- 解析并执行 output schema 校验。

**修复结果**
- 若 schema 通过：`status=success`；
- `repair_level=deterministic_generic`；
- `warnings` 追加 `OUTPUT_REPAIRED_GENERIC`；
- 允许写入 cache。

### 示例 2：Envelope 中 response 字段包含 JSON 字符串

**原始输出（stdout）**

```json
{
  "session_id": "xxx",
  "response": "{\"digest_path\":\"...\",\"references_path\":\"...\",\"provenance\":{\"generated_at\":\"...\",\"input_hash\":\"sha256:...\",\"model\":\"gemini-3-pro-preview\"},\"warnings\":[],\"error\":null}"
}
```

**修复动作**
- 识别 envelope 结构；
- 提取 `response` 文本作为候选；
- 尝试 JSON 解析并做 schema 校验。

**修复结果**
- schema 通过则 success，标记 `repair_level=deterministic_generic` + warning；
- schema 不通过则 failed（不做语义补字段）。

### 示例 3：混杂文本 + 首个 JSON 对象

**原始输出（stdout）**

```text
The task is complete.
Result:
{"digest_path":"...","references_path":"...","provenance":{"generated_at":"...","input_hash":"sha256:...","model":"gemini-3-pro-preview"},"warnings":[],"error":null}
附加统计信息...
```

**修复动作**
- 去除首尾噪声；
- 提取 first-json-object；
- 解析并校验 schema。

**修复结果**
- schema 通过：success + `repair_level=deterministic_generic` + warning + 可缓存；
- 不通过：failed。

### 示例 4：可解析 JSON 但字段不满足 schema（修复失败）

**原始输出（stdout）**

```json
{"digest_path":".../artifacts/digest.md","references_path":".../artifacts/references.json"}
```

**修复动作**
- 解析成功，但仅做 deterministic 处理，不补语义字段；
- 进入 schema 校验。

**修复结果**
- 因缺少必填字段（如 `provenance`/`warnings`/`error`）而 failed；
- `repair_level` 保持 `none` 或记录为未成功修复态（实现时按结果模型约定）；
- 不写 cache。
