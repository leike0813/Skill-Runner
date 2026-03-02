## Context

Skill-Runner 项目经 v0.2→v0.3 架构重构，代码从扁平模块（`server/adapters/`、`server/services/`）迁移至组件化/分层结构（`server/engines/`、`server/runtime/`、`server/services/{orchestration,platform,skill,ui}/`）。协议层文档（FCMP、statechart、schema contract）维护良好，100% 一致。但代码结构映射类文档（目录树、组件清单、SSOT 导航表、开发指南）整体未同步，一致率仅 10%。

**现状**: 开发者/AI 协作者依赖 AGENTS.md SSOT 表定位文件，当前 7 条路径指向不存在的位置。`docs/project_structure.md` 和 `docs/core_components.md` 描述的目录树和组件与实际代码完全不符。

## Goals / Non-Goals

**Goals:**
- 修正 AGENTS.md SSOT 导航表中的 7 条过期路径
- 修正 `docs/session_runtime_statechart_ssot.md` 中的实现锚点路径
- 重写 `docs/project_structure.md` 反映当前实际目录结构
- 重写 `docs/core_components.md` 覆盖当前分层架构全部核心模块
- 更新 `README.md` 补充 OpenCode 引擎、鉴权说明
- 为 `docs/dev_guide.md` 添加归档标注
- 更新 `docs/adapter_design.md` 和 `docs/test_framework_design.md` 局部过期内容

**Non-Goals:**
- 不修改任何 Python 源代码
- 不修改协议/合同文档（已一致）：`runtime_stream_protocol.md`, `runtime_event_schema_contract.md`, `session_fcmp_invariants.yaml`, `session_event_flow_sequence_fcmp.md`, `api_reference.md`
- 不重构 `docs/dev_guide.md` 全文（仅添加归档标注，保留历史参考价值）
- 不建立 CI 防漂移自动化（属于后续 P3 改进）

## Decisions

### D1: 分阶段执行（P0 → P1 → P2）

P0（路径修正）先行，因为 AGENTS.md 是 AI 协作者的首要入口，影响最广。P1（结构重写）次之，影响新开发者上手。P2（局部更新）最后，影响范围较小。

**替代方案**: 一次性更新所有文档。**否决理由**: 8 篇文档同时重写风险较大，分阶段可逐步验证。

### D2: dev_guide.md 归档而非删除

`dev_guide.md` 中 §5（Skill 包结构规范）、§6（引擎适配约定）、§7（规范化链定义）仍有规范参考价值。添加归档标注比删除更安全。

**替代方案**: 删除文件并将有效内容提取到新文档。**否决理由**: 提取工作量大，且原文中包含与 Codex 的对话上下文（§15 工作指令），具有历史参考意义。

### D3: project_structure.md 从实际文件系统生成目录树

使用 `tree` 或 `find` 命令生成当前 `server/` 目录树，确保结构准确无手工偏差。

### D4: core_components.md 按分层架构重新组织

以 4 层为主线：Runtime 层 → Services 层 → Engines 层 → Routers 层。每个组件标注实际路径、职责、关键接口。

## Risks / Trade-offs

- **[文档时效性]**: 重写的文档在下一次代码重构时仍可能过期 → **缓解**: 在 AGENTS.md checklist 中强调路径变更同步更新文档的规则
- **[信息密度]**: core_components.md 覆盖全部模块可能导致文档过长 → **缓解**: 只列出核心模块和其路径/职责，不深入方法级细节（方法级在 api_reference.md）
- **[dev_guide 归档标注可能被忽略]**: 添加标注后开发者仍可能参考过期内容 → **缓解**: 归档标注放在文件最前方，使用醒目的告警格式
