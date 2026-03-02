## Purpose

确保 `docs/dev_guide.md` 所有章节（§0–§16）内容准确反映当前 v0.3+ 代码库实现，所有文件路径引用真实存在于文件系统中。

## Requirements

### Requirement: 所有代码路径引用必须存在
`dev_guide.md` 中引用的 `server/**/*.py` 路径 SHALL 全部对应项目中实际存在的文件。

#### Scenario: 路径全量校验
- **WHEN** 使用 `grep -oP 'server/[a-zA-Z0-9_/]+\.py'` 从 `dev_guide.md` 提取全部路径
- **THEN** 每一个路径通过 `test -f` 验证为存在

### Requirement: 引擎列表与实际引擎目录对齐
文档中列出的引擎清单 SHALL 与 `server/engines/` 下的子包（排除 `common/` 和 `__pycache__/`）一一对应。

#### Scenario: 引擎目录一致性
- **WHEN** 列出 `server/engines/` 下的子目录
- **THEN** 文档 §3/§6 中列出的引擎（Codex、Gemini、iFlow、OpenCode）与目录完全匹配

### Requirement: 工作区布局与实际 run 目录对齐
§4 描述的工作区目录结构 SHALL 与 `data/runs/<run_id>/` 中的实际文件布局一致。

#### Scenario: run 目录结构验证
- **WHEN** 检查 `data/runs/` 中任一已完成 run 的文件树
- **THEN** 文档描述的目录/文件（`.audit/`、`bundle/`、`status.json`、`input.json`、`result/result.json` 等）均可匹配

### Requirement: REST API 路由列表与代码注册路由对齐
§9 列出的 API 端点 SHALL 涵盖 `server/routers/*.py` 中实际注册的所有 `@router.*` 路由。

#### Scenario: 路由覆盖率
- **WHEN** 扫描 `server/routers/` 中全部 router 文件的路由装饰器
- **THEN** 文档 §9 中列出的端点覆盖 100% 的路由（或对未列出的路由给出明确说明）

### Requirement: 架构组件描述与实际模块对齐
§3 列出的组件列表 SHALL 与 `docs/core_components.md` 中的组件描述保持一致，不产生矛盾。

#### Scenario: 交叉文档一致性
- **WHEN** 对比 `dev_guide.md` §3 与 `docs/core_components.md` 的组件列表
- **THEN** 组件命名、归属层级、职责描述无矛盾

### Requirement: 归档标记移除
重写后的 `dev_guide.md` SHALL NOT 包含 `[!CAUTION]` 归档警告块。

#### Scenario: 归档标记检查
- **WHEN** 检查文件头部
- **THEN** 不存在 `> [!CAUTION]` 或 `ARCHIVED` 标记

### Requirement: 配置系统描述与实际实现对齐
§10 技术栈/配置相关描述 SHALL 与 `server/core_config.py` 的 yacs 配置体系以及实际环境变量名保持一致。

#### Scenario: 环境变量名验证
- **WHEN** 提取文档中引用的 `SKILL_RUNNER_*` 环境变量名
- **THEN** 每个变量名在 `server/core_config.py` 或 `server/config.py` 中有对应引用
