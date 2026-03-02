> **⚠️ 纯文档工作 — 不修改任何代码文件**

## 1. 文档头部与项目定义（§0–§2）

- [x] 1.1 移除 `[!CAUTION]` 归档标记，恢复正式文档头部（Version → v0.3+）
- [x] 1.2 重写 §0（项目定义）：补充 4 引擎、interactive 会话、inline TUI
- [x] 1.3 更新 §1（核心需求）：标注 R1-R6 的实现状态，补充 R3 引擎完整列表
- [x] 1.4 更新 §2（非目标）：调整 N3 鉴权描述（已有 OAuth 但非复杂权限系统）

## 2. 架构与工作区（§3–§4）

- [x] 2.1 重写 §3（总体架构）：按 4 层架构（Runtime/Services/Engines/Routers）描述组件；新增 Auth Manager、FCMP Protocol、Session Statechart、Observability、Skill Patcher
- [x] 2.2 重写 §4（工作区约定）：按实际 `data/runs/<run_id>/` 布局重写（`.audit/`+attempt 分区、`bundle/`、`status.json`）

## 3. Skill 包与引擎适配（§5–§6）

- [x] 3.1 更新 §5（Skill 包结构）：更新 `runner.json` 字段为当前已实现 schema；补充 temp-skill-runs 与 Skill Patcher 流程
- [x] 3.2 重写 §6（引擎适配）：统一为 `BaseExecutionAdapter` 4 阶段管线描述；更新配置加载逻辑；补充 OpenCode 策略；更新 interactive 会话机制

## 4. 输出校验与 Artifacts（§7–§8）

- [x] 4.1 更新 §7（输出校验与规范化链）：对齐 `_parse_output` + `AdapterTurnResult` 实际流程
- [x] 4.2 更新 §8（Artifacts 管理）：描述 bundle 生成流程（manifest.json + debug manifest + zip）

## 5. REST API（§9）

- [x] 5.1 全面更新 §9（REST API）：对齐 8 个 router 文件（skills/jobs/engines/management/skill_packages/temp_skill_runs/ui/oauth_callback）的路由列表和请求/响应模型

## 6. 技术栈、安全、杂项（§10–§16）

- [x] 6.1 更新 §10（技术栈）：Python 3.12+、yacs 配置、Jinja2、容器化说明
- [x] 6.2 更新 §11（安全/权限）：补充 OAuth 鉴权、Trust Folder、inline TUI profile
- [x] 6.3 替换 §12（里程碑）：移除旧规划，替换为版本演进简史（v0→v0.2→v0.3）
- [x] 6.4 更新 §13（示例 Skill）：对齐 `tests/fixtures/skills/` 实际列表
- [x] 6.5 处理 §14（待决问题）：替换为环境变量参考表
- [x] 6.6 移除 §15（Codex 工作指令）：规划性内容不再适用
- [x] 6.7 更新 §16（日志配置）：对齐 `server/logging_config.py` 实际行为

## 7. 验证

- [x] 7.1 全量路径校验：提取 `dev_guide.md` 中所有 `server/**/*.py` 路径，逐一验证存在性
- [x] 7.2 交叉文档一致性检查：对比 §3 组件列表与 `docs/core_components.md`
- [x] 7.3 引擎目录一致性检查：对比文档引擎列表与 `server/engines/` 实际子目录
