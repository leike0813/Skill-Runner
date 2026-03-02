## Why

当前模型已从单一 `server/models.py` 拆到多个 `server/models_*.py`，但仍位于 `server/` 根目录，目录语义与 Python 社区常见组织方式不一致，且持续增加根目录噪声。将其收敛为 `server/models/` 包可明确责任边界，并降低后续维护与扩展成本。

## What Changes

- 将现有模型实现从 `server/models.py` + `server/models_*.py` 迁移为 `server/models/` 包内领域模块（`common/run/skill/engine/interaction/management/runtime_event/error`）。
- 将 `server.models` 对外入口迁移到 `server/models/__init__.py`，维持 `from server.models import X` 兼容导出。
- 全仓内部导入路径统一为包内路径（如 `server.models.common` 或包内相对导入），移除 `server.models_*` 旧路径依赖。
- 更新结构守卫测试与文档，确保后续不再回退到 `server/` 根目录散落 `models_*.py` 的组织方式。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `models-module-boundary`: 将“模型按领域拆分”要求收敛到 `server/models/` 包级边界，并补充对旧根目录模块形态的禁止约束与结构守卫要求。

## Impact

- Affected code:
  - `server/models.py`
  - `server/models_*.py`（`common/run/skill/engine/interaction/management/runtime_event/error`）
  - 直接依赖上述模块路径的内部导入点与测试
- Affected APIs:
  - 对外 HTTP API 无变化
  - runtime schema/invariants 无变化
  - `from server.models import X` 兼容导入保持不变
- Dependencies:
  - 无新增外部依赖

