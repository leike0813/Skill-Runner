## ADDED Requirements

### Requirement: UI inline TUI capability SHALL come from engine shell capability provider
UI shell 管理器 MUST 通过统一 capability provider 解析命令参数、sandbox 探测、安全配置与鉴权提示，并且 MUST NOT 在主流程保留 per-engine 分支。

#### Scenario: 启动 inline TUI 会话
- **WHEN** 用户选择任一 engine 启动会话
- **THEN** manager 从 capability provider 获取启动能力
- **AND** manager 不直接维护 engine-specific 规则分支

### Requirement: Engine model refresh lifecycle SHALL route through unified catalog lifecycle
Engine model refresh actions in UI MUST route through a unified catalog lifecycle registry and MUST NOT directly depend on a single-engine catalog implementation.

#### Scenario: 手动刷新 opencode models
- **WHEN** 调用 `/ui/engines/opencode/models/refresh`
- **THEN** 路由通过统一 lifecycle 调用 refresh
- **AND** 不直接 import engine 专属 catalog 对象
