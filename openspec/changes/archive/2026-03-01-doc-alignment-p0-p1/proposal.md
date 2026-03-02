## Why

项目 v0.2→v0.3 期间进行了架构级重构（`server/adapters/` → `server/engines/`、`server/services/` 拆包、新增 `server/runtime/` 层），但代码结构映射类文档整体未同步更新。经过对 15 篇文档的交叉核验，协议/合同文档一致率 100%，而代码结构映射文档一致率仅 10%，形成显著知识落差。AGENTS.md 的 SSOT 导航表引用了 7 条过期路径，可能导致开发者/AI 协作者查找歧义。

> **本轮 change 为纯文档类任务，不修改任何源代码。**

## What Changes

**P0: 关键路径修正**
- 更新 `AGENTS.md` 中 7 条 SSOT 源代码路径引用
- 更新 `docs/session_runtime_statechart_ssot.md` 中 3 处实现锚点路径

**P1: 结构类文档重写**
- 重写 `docs/project_structure.md`：反映当前 `server/engines/`、`server/runtime/`、`server/services/{orchestration,platform,skill,ui}/`、`server/routers/` 实际结构
- 重写 `docs/core_components.md`：以当前分层架构为主线重新描述组件，覆盖 runtime/services/engines/routers 全部核心模块
- 更新 `README.md`：添加 OpenCode 引擎、更新架构简述、更新鉴权说明

**P2: 设计类文档局部更新**
- 在 `docs/dev_guide.md` 文件头添加归档标注（v0.2 规划文档，仅供历史参考）
- 更新 `docs/adapter_design.md`：方法签名对齐当前组件模型、标记 §3 重构计划为已完成
- 更新 `docs/test_framework_design.md`：单元测试目录规划对齐当前 120+ 测试文件分类

## Capabilities

### New Capabilities
_无。本轮仅文档修正，不引入新能力。_

### Modified Capabilities
_无。不涉及 spec-level 行为变更。_

## Impact

- **代码**: 无源码变更
- **文档**: 8 篇 Markdown 文件将被修改
- **AGENTS.md**: SSOT 导航表路径更正（开发者/AI 依赖此表定位文件）
- **风险**: 极低（纯文档修正，不影响运行时行为）
- **验证**: 修正后路径可通过 `test -f <path>` 全量校验
