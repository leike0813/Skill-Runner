## Context

`docs/dev_guide.md` 当前为 v0.2.0 规划文档（700 行），因多次追记已成"规划 + 部分实现注释"的混合体。在上一轮 `doc-alignment-p0-p1` change 中加了归档标记，但用户希望将其重写为当前实现的技术参考文档。

当前实现与 v0.2 规划的主要差异已在 `proposal.md` 中列出。本 change 仅修改 `docs/dev_guide.md` 一个文件，不涉及任何代码变更。

核心约束：
- 需与 `docs/project_structure.md`、`docs/core_components.md`、`docs/adapter_design.md` 等已对齐文档保持一致
- 所有文件路径引用必须可通过 `test -f` 验证
- 文档语言保持中文

## Goals / Non-Goals

**Goals:**
- 将 `dev_guide.md` 转变为准确反映 v0.3+ 实现的技术参考文档
- 移除归档标记，使其恢复为活跃文档
- 所有代码路径引用与当前实际文件系统对齐
- 保持与其他文档的交叉一致性

**Non-Goals:**
- 不修改任何代码文件
- 不新增/修改 API 接口
- 不撰写架构演进 RFC（仅记录当前状态）
- 不做信息合并（不尝试把 adapter_design.md 或 test_framework_design.md 的内容合并过来——保持各文档独立职责）

## Decisions

### D1. 保留原章节编号体系
**选择**：保留 §0–§16 编号结构，仅更新内容
**理由**：外部引用（如 AGENTS.md、README.md 中的 cross-ref）可能引用章节编号；保持编号稳定减少连锁修改
**替代方案**：重新编号——增加其他文档适配成本

### D2. 移除规划性章节而非标记为已完成
**选择**：§12（里程碑）替换为版本演进简史；§14（待决问题）移除已解决项；§15（Codex 工作指令）整段移除
**理由**：保留规划性内容会与"当前实现文档"定位矛盾，造成阅读混乱
**替代方案**：加 `[COMPLETED]` 标记——增加噪声，对新读者不友好

### D3. §4 工作区约定由实际 run 目录反推
**选择**：使用 `data/runs/<run_id>/` 实际文件列表重写布局
**理由**：实际布局使用 `.audit/`（含 attempt 后缀）+ `bundle/` + `status.json`，与规划文档的 `logs/raw/result/` 完全不同

### D4. §6 统一为 BaseExecutionAdapter 4 阶段管线描述
**选择**：用 `_construct_config → _build_prompt → _execute_process → _parse_output` 管线替代原 `EngineAdapter.run()` 接口描述
**理由**：这是当前所有引擎的实际统一接口，已在 adapter_design.md 中对齐

### D5. 按 section 拆分为独立 task，方便断点续做
**选择**：每 1-3 个相关 section 为一个 task
**理由**：700 行全文重写风险高；按 section 拆分可逐步验证

## Risks / Trade-offs

- **[信息遗漏]** 原文中有些规划性讨论（如规范化链 N0-N3 分层）在当前实现中可能已简化但仍有价值 → **缓解**：保留规范化链的分层描述但标注当前实际实现范围
- **[交叉引用漂移]** 重写后其他文档中引用 dev_guide 特定段落的链接可能失效 → **缓解**：保持章节编号稳定（D1）；且当前无其他文档直接引用 dev_guide 的特定行号
- **[文档长度]** 700 行全面重写可能导致篇幅膨胀 → **缓解**：对已有独立文档详细描述的主题（如 adapter_design.md、session_runtime_statechart_ssot.md），仅给出简述 + 交叉引用链接
