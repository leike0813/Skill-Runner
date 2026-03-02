## Context

当前 broad catch allowlist 基线（`server/`）为：
- total: 65
- pass: 8
- loop_control: 1
- return: 8
- log: 37
- other: 11

wave7 聚焦热点：
- `server/engines/iflow/adapter/config_composer.py`: total 4
- `server/engines/gemini/adapter/config_composer.py`: total 3
- `server/engines/codex/adapter/config/toml_manager.py`: total 3
- `server/services/skill/skill_package_manager.py`: total 4

这些模块以配置解析、文件 IO、记录转换为主，异常域相对可判定，适合“可收窄优先 + 保守兼容”推进。

## Goals / Non-Goals

**Goals:**
- 在上述 4 个目标文件优先收窄 deterministic broad catch，继续压降 allowlist 基线。
- 对必须保留的 broad catch 明确兼容理由并补齐结构化诊断信息。
- 保持 engine 配置生成与 skill package 管理行为兼容。

**Non-Goals:**
- 不改 HTTP API 契约。
- 不改 runtime schema/invariants。
- 不进行跨模块重构，不引入新依赖。

## Decisions

### 1) Wave7 实施顺序
1. `iflow/gemini` adapter `config_composer`
2. codex adapter `config/toml_manager`
3. `skill_package_manager`
4. allowlist 更新 + 门禁回归

理由：先处理 adapter config 路径可快速降低 broad catch，之后处理 skill package 管理路径以完成整波收敛。

### 2) 收窄规则
- JSON/TOML 解析：优先 `json.JSONDecodeError`、`tomlkit` 相关异常
- 文件 IO：优先 `OSError` / `UnicodeDecodeError`
- 类型转换与值解析：优先 `TypeError` / `ValueError`
- 仅对无法稳定枚举的边界场景保留 broad catch，并要求 structured log

### 3) 兼容性护栏
- 不改变 adapter 配置输出结构与默认值回退语义。
- 不改变 skill package 安装状态、错误映射与路由层可观测行为。
- 不改 runtime 事件协议与状态机语义。

### 4) 验证门禁
- `tests/unit/test_no_unapproved_broad_exception.py`
- `tests/unit/test_codex_config.py`
- `tests/unit/test_codex_config_fusion.py`
- `tests/unit/test_gemini_adapter.py`
- `tests/unit/test_iflow_adapter.py`
- `tests/unit/test_skill_package_manager.py`
- `tests/unit/test_skill_packages_router.py`

## Risks / Trade-offs

- [Risk] 收窄后暴露此前被吞没的配置异常。  
  → Mitigation: 仅收窄 deterministic 分支，保留现有 fallback 语义。

- [Risk] 适配器差异导致异常域枚举不完整。  
  → Mitigation: 对不确定边界保留受控 broad catch 并补结构化日志。

- [Risk] allowlist 基线更新遗漏导致门禁失败。  
  → Mitigation: 将 allowlist 更新与 AST 门禁设为波次末尾必跑步骤。

## Migration Plan

1. 按 wave7 顺序逐文件收窄并保持行为兼容。  
2. 每个模块改完即跑对应测试。  
3. 更新 allowlist 到新基线并跑 AST 门禁。  
4. 完成本波回归后进入归档评审。  

## Open Questions

- _None._
