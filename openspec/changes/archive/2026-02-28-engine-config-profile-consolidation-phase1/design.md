## Design Summary

本 change 将 adapter 侧“引擎资产路径配置”彻底集中到 `adapter_profile.json`，并把 `core_config` 收敛为系统级公共配置。

目标是形成单一责任边界：
1. `core_config`: 系统级、跨引擎共享配置。
2. `adapter_profile`: 引擎执行资产与模型目录元信息。
3. `config_composer/model_registry`: 仅消费 profile，不再硬编码路径。

## Architecture

### 1) Adapter Profile 扩展

在现有 profile（prompt/session/workspace）基础上新增两段：

1. `config_assets`
   - `bootstrap_path`
   - `default_path`
   - `enforced_path`
   - `settings_schema_path`（可选，按引擎）
   - `skill_defaults_path`（可选，按引擎）
2. `model_catalog`
   - `mode`: `manifest` | `runtime_probe`
   - `manifest_path`（`manifest` 模式必填）
   - `models_root`（可选，默认推导）
   - `seed_path`（动态目录引擎可选）

上述字段纳入 `adapter_profile_schema.json`，并由 `profile_loader` fail-fast 校验。

### 2) 路径读取统一

1. `config_composer.py` 不再使用 `Path(__file__).resolve().parents[...]` 拼接路径。
2. 路径全部经 `execution_adapter -> profile_loader -> AdapterProfile` 下发。
3. `model_registry.py` 的 models root / manifest 查找改为从 profile 读取。

### 3) Core Config 收敛

移除仅服务于 adapter 的引擎专属配置（例如 prompt template path 等），保留：
1. 系统根路径、缓存目录、运行目录
2. 超时、调度、并发等跨引擎策略
3. 与 adapter 无关的 auth/runtime 全局配置

### 4) 兼容策略

1. 对外 API 与 UI 语义保持不变。
2. profile 缺失或非法时直接 fail-fast，避免运行时隐式回退。
3. 行为一致性通过现有 adapter 回归测试保障（start/resume/parse/session-handle）。

## File-Level Changes

1. 修改 `server/assets/schemas/adapter_profile_schema.json`
   - 扩展 `config_assets` 与 `model_catalog` 字段及约束。
2. 修改 `server/runtime/adapter/common/profile_loader.py`
   - 增加新字段解析与强校验。
3. 修改四个 `server/engines/*/adapter/adapter_profile.json`
   - 补齐资产路径与模型目录元信息。
4. 修改四个 `server/engines/*/adapter/config_composer.py`
   - 改为基于 profile 取路径。
5. 修改 `server/services/model_registry.py`
   - 引擎模型 manifest/root 路径从 profile 获取。
6. 修改 `server/core_config.py`
   - 删除 adapter 专属引擎键，保留系统级配置。

## Risks and Mitigations

1. 风险：profile 配置迁移不完整导致启动失败。
   - 控制：registry 初始化时全量校验 profile；测试覆盖缺字段场景。
2. 风险：manifest 路径切换引发模型接口回归。
   - 控制：回归 `test_model_registry.py` 与 `test_v1_routes.py` 相关模型接口用例。
3. 风险：config composer 路径来源切换后引擎默认配置丢失。
   - 控制：保留 default/enforced 叠层顺序断言测试。
