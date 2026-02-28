## ADDED Requirements

### Requirement: Legacy compatibility imports MUST be removed in phase2
phase2 后，adapter/runtime 相关旧路径兼容导入层 MUST NOT 存在。

#### Scenario: Compatibility layer cleanup
- **WHEN** 完成 phase2 收口
- **THEN** 不存在仅用于兼容旧路径的 re-export 模块
- **AND** 全仓引用均指向新目录结构

### Requirement: Trust strategy MUST be adapter-local and centrally dispatched
run folder trust 策略 MUST 以引擎 adapter 层实现，并由 orchestration trust manager 统一调度。

#### Scenario: Adapter-local trust strategy placement
- **WHEN** 为引擎实现 run folder trust
- **THEN** codex 与 gemini 策略分别位于 `server/engines/codex/adapter/trust_folder_strategy.py` 与 `server/engines/gemini/adapter/trust_folder_strategy.py`
- **AND** `server/services/orchestration/run_folder_trust_manager.py` 内部不出现 `if engine == ...` 分支
- **AND** 未注册策略引擎自动使用 registry 内置 noop fallback

### Requirement: Legacy orchestration compatibility shells MUST NOT exist
phase2 收口后，orchestration 目录中的兼容壳文件 MUST 被删除。

#### Scenario: Compatibility shell cleanup
- **WHEN** 完成 phase2 增量收口
- **THEN** 以下文件不存在：
  - `server/services/orchestration/codex_config_manager.py`
  - `server/services/orchestration/config_generator.py`
  - `server/services/orchestration/opencode_model_catalog.py`
