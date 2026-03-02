## Why

`docs/dev_guide.md` 是 v0.2.0 阶段的开发规划文档，距今已经历 v0.3+ 多个版本迭代。当前内容与实际实现存在系统性偏差：架构从 3 引擎扩展到 4 引擎（+OpenCode）、工作区布局从 `logs/raw/result/` 演进为 `.audit/` + attempt 分区、新增 FCMP 事件协议取代简单 JSONL events、新增 OAuth 鉴权子系统、新增 Session 状态机与 inline TUI、Skill 包管理与 Patcher 子系统、配置从 YAML 演进为 yacs + 环境变量等。大量待决问题（§14）和里程碑计划（§12）作为规划文档已不再适用。

本 change 将 `dev_guide.md` 从"v0.2.0 规划 + 部分追记"**重写**为反映当前实现的技术参考文档，同时移除归档标记。

> **⚠️ 本 change 为纯文档类工作，不修改任何代码文件。**

## What Changes

- **移除**归档警告标记（`[!CAUTION]` 块），恢复为正式文档
- **§0 项目定义**：更新为 4 引擎（Codex/Gemini/iFlow/OpenCode）并补充 interactive 会话能力
- **§1 核心需求**：标注已实现状态；补充 R3 多引擎已全部落地；补充 OpenCode 引擎
- **§2 非目标**：更新 N3 鉴权说明（已有 OAuth 体系但非复杂权限系统）
- **§3 总体架构**：按当前 4 层架构（Runtime / Services / Engines / Routers）重写；新增 Auth Manager、FCMP Protocol、Session Statechart、Observability、Skill Patcher 等组件
- **§4 工作区约定**：按实际 run 目录布局重写（`.audit/` attempt 分区 + `bundle/` + `status.json`）
- **§5 Skill 包结构**：更新 `runner.json` schema 为当前实现；补充 Skill Patcher、temp-skill-runs 流程
- **§6 引擎适配**：更新统一 Adapter 接口为 `BaseExecutionAdapter` 4 阶段管线（construct_config → build_prompt → execute_process → parse_output）；更新配置加载逻辑；补充 OpenCode 策略
- **§7 输出校验与规范化**：更新为当前实际解析流程（`_parse_output` + `AdapterTurnResult`）
- **§8 Artifacts 管理**：更新 bundle 生成流程（manifest.json + debug manifest）
- **§9 REST API 设计**：全面更新路由列表及请求/响应模型，对齐当前 8 个 router 文件
- **§10 技术栈**：更新 Python 3.12+、yacs、Jinja2 等依赖；更新 Docker/容器化说明
- **§11 安全/权限**：补充 OAuth 鉴权、Trust Folder、inline TUI 安全策略
- **§12 里程碑**：移除旧里程碑，替换为版本演进简史
- **§13 示例 Skill**：更新为当前 fixture skills 列表
- **§14 待决问题**：移除已解决问题，仅保留真正未决项（如有）
- **§15 工作指令**：移除（已完成开发）
- **§16 日志配置**：更新为当前 logging_config.py 的实际行为

## Capabilities

### New Capabilities
- `dev-guide-accuracy`: 要求 `dev_guide.md` 所有章节内容与当前代码实现一致，所有文件路径引用可验证为存在

### Modified Capabilities
_无（本 change 不修改现有 spec 的需求定义）_

## Impact

- **修改文件**：`docs/dev_guide.md`（唯一文件）
- **不影响代码**：无代码修改、无 API 变更、无测试变更
- **交叉引用**：需与 `docs/project_structure.md`、`docs/core_components.md`、`docs/adapter_design.md`、`docs/session_runtime_statechart_ssot.md`、`AGENTS.md` 保持表述一致
