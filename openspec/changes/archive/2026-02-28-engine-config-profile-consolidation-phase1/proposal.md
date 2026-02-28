## Why

当前引擎相关配置分散在 `core_config`、adapter 代码常量和 assets 路径硬编码中，导致职责边界不清晰，新增引擎或迁移配置时需要跨多处同步，容易漂移。

同时，adapter profile 已成为引擎执行侧的单源配置入口，但尚未承载“引擎资产路径与模型目录元数据”，使 profile 的可移植性和可审计性不足。

## What Changes

1. 将引擎相关配置进一步下沉到各引擎 `adapter_profile.json`，包括：
   - 配置资产路径（`bootstrap/default/enforced`）
   - 运行时 schema 路径（按引擎需要）
   - 模型目录/manifest 路径（或动态 catalog 元信息）
2. 清理 `server/core_config.py` 中仅用于 adapter 的引擎配置键，保留系统级与跨引擎公共配置。
3. 将 adapter 侧配置读取统一为“profile 驱动”，移除 adapter/composer 中的路径硬编码。
4. 保持对外 API 与 UI 行为不变，仅做内部配置职责收敛。

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `engine-adapter-runtime-contract`: adapter profile 从“prompt/session/workspace 三段”扩展为“引擎执行资产单源”，并要求 fail-fast 校验。
- `engine-runtime-config-layering`: 运行时配置分层中的资产路径解析来源改为 adapter profile，不再依赖 `core_config` 的引擎专属键或 adapter 代码硬编码。

## Impact

1. 影响代码：
   - `server/runtime/adapter/common/profile_loader.py`
   - `server/assets/schemas/adapter_profile_schema.json`
   - `server/engines/*/adapter/adapter_profile.json`
   - `server/engines/*/adapter/config_composer.py`
   - `server/services/model_registry.py`（模型目录/manifest 路径来源收敛）
   - `server/core_config.py`（移除 adapter 专属引擎配置项）
2. 不影响公共接口：
   - `/v1`、`/ui` 路由契约不变
   - 仅内部配置来源与装配路径变更
3. 测试与文档：
   - 新增 profile 资产路径校验与解析测试
   - 更新开发者文档中的“引擎配置责任边界”
