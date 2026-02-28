## ADDED Requirements

### Requirement: Built-in E2E runtime options UI MUST follow context-aware visibility
E2E 客户端 runtime options 区域 MUST 根据 run source 与 execution mode 控制可见性，避免无效配置暴露。

#### Scenario: debug_keep_temp visibility
- **WHEN** 运行链路为后端内建 skill（installed source）
- **THEN** `debug_keep_temp` 不显示
- **AND** 仅在临时上传 skill（temp source）显示该选项

#### Scenario: interactive options visibility
- **WHEN** `execution_mode != interactive`
- **THEN** `interactive_auto_reply` 与 `interactive_reply_timeout_sec` 均不显示

#### Scenario: timeout field visibility in interactive mode
- **WHEN** `execution_mode=interactive` 且 `interactive_auto_reply=false`
- **THEN** `interactive_reply_timeout_sec` 不显示
- **AND** `interactive_auto_reply` 以 checkbox 显示

#### Scenario: timeout field visible for auto reply
- **WHEN** `execution_mode=interactive` 且 `interactive_auto_reply=true`
- **THEN** 显示 `interactive_reply_timeout_sec` 输入框

### Requirement: Built-in E2E runtime option labels MUST use configured Chinese copy
E2E runtime options 展示文案 MUST 使用中文标签。

#### Scenario: Runtime option labels
- **WHEN** 用户查看 runtime options 区域
- **THEN** 文案包含：
- **AND** `no_cache=禁用缓存机制`
- **AND** `debug=Debug模式`
- **AND** `debug_keep_temp=保留上传的临时 Skill 包（Debug用）`
- **AND** `interactive_auto_reply=超时自动回复`
- **AND** `interactive_reply_timeout_sec=回复超时阈值`
