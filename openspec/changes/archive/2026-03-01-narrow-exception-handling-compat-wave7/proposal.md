## Why

wave6 后，`server/` 范围 broad catch 基线降至 `65`，剩余高密度主要集中在 adapter 配置与 skill package 管理链路。上述路径仍有多处可类型化的解析/IO broad catch，持续影响异常可诊断性与 allowlist 收敛效率，因此需要开启 wave7 继续做兼容优先的增量收窄。

## What Changes

- 聚焦 `server/engines/iflow/adapter/config_composer.py` 与 `server/engines/gemini/adapter/config_composer.py`，收窄 deterministic 配置解析/转换 broad catch。
- 聚焦 `server/engines/codex/adapter/config/toml_manager.py`，收窄 TOML/文件处理 broad catch。
- 聚焦 `server/services/skill/skill_package_manager.py`，收窄 package 安装与记录处理中的 broad catch，并保持现有 fallback 语义。
- 对必要保留的边界 broad catch 补齐结构化诊断字段（`component/action/error_type/fallback`）。
- 同步更新 `docs/contracts/exception_handling_allowlist.yaml` 基线并通过 AST 门禁与模块回归。

## Capabilities

### New Capabilities
- _None._

### Modified Capabilities
- `exception-handling-hardening`: 增加 wave7 对 adapter config + skill package 管理热点的收窄约束与基线递减要求。

## Impact

- Affected code:
  - `server/engines/iflow/adapter/config_composer.py`
  - `server/engines/gemini/adapter/config_composer.py`
  - `server/engines/codex/adapter/config/toml_manager.py`
  - `server/services/skill/skill_package_manager.py`
  - `docs/contracts/exception_handling_allowlist.yaml`
  - `tests/unit/test_no_unapproved_broad_exception.py`（门禁回归）
- Public API: 无 breaking change。
- Runtime schema/invariants: 不修改。
- Compatibility: 保持 engine config 生成语义与 skill package 管理对外行为不变。
