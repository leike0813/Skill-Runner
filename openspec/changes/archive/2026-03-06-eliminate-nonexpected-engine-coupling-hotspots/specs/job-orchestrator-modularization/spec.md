## ADDED Requirements

### Requirement: Orchestrator MUST 使用 engine profile 解析 workspace 与快照忽略规则
编排层不得硬编码 engine dot-directory 前缀或快照排除目录。相关规则 MUST 由 engine profile/registry 统一提供。

#### Scenario: 新引擎接入不改 orchestrator 映射表
- **WHEN** 新增一个 engine profile（含 workspace_subdir）
- **THEN** orchestrator 可按 profile 解析技能目录
- **AND** 无需修改本地 engine 前缀映射表

### Requirement: Trust 路径默认值 MUST 由 engine trust strategy 层负责
orchestrator trust manager 不得再维护 codex/gemini 默认配置路径硬编码，默认路径解析 MUST 下沉到 trust strategy 注册层。

#### Scenario: 运行 trust manager 未显式传入路径
- **WHEN** trust manager 以默认参数初始化
- **THEN** 仍可解析 codex/gemini trust 配置路径
- **AND** orchestrator 层不包含默认路径拼接逻辑

