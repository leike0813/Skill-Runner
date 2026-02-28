## 1. OpenSpec

- [x] 1.1 完成 `proposal/design/specs/tasks` 四工件
- [x] 1.2 执行 `openspec validate engine-config-profile-consolidation-phase1 --type change`

## 2. Profile Schema & Loader

- [x] 2.1 扩展 `adapter_profile_schema.json`：新增 `config_assets` 与 `model_catalog`
- [x] 2.2 扩展 `profile_loader.py`：解析新增字段并 fail-fast 校验
- [x] 2.3 新增/更新 profile loader 单测（缺字段、枚举非法、路径非法）

## 3. Engine Profiles

- [x] 3.1 更新 `server/engines/codex/adapter/adapter_profile.json`
- [x] 3.2 更新 `server/engines/gemini/adapter/adapter_profile.json`
- [x] 3.3 更新 `server/engines/iflow/adapter/adapter_profile.json`
- [x] 3.4 更新 `server/engines/opencode/adapter/adapter_profile.json`

## 4. Adapter Wiring

- [x] 4.1 四引擎 `config_composer.py` 改为从 profile 读取 `bootstrap/default/enforced/schema` 路径
- [x] 4.2 删除 adapter/composer 中遗留路径硬编码

## 5. Model Catalog Wiring

- [x] 5.1 `model_registry.py` 改为从 profile 读取 `models_root/manifest_path`
- [x] 5.2 保持 opencode 动态 catalog 行为不变，仅统一路径来源
- [x] 5.3 更新模型相关回归测试（manifest 读取与快照解析）

## 6. Core Config Cleanup

- [x] 6.1 从 `core_config.py` 移除 adapter 专属引擎配置键
- [x] 6.2 保留系统级公共配置并更新注释边界
- [x] 6.3 更新受影响测试与文档

## 7. Validation

- [x] 7.1 运行 adapter + model registry 相关 pytest 子集
- [x] 7.2 运行改动文件集 mypy
- [x] 7.3 确认对外 `/v1`、`/ui` 行为无回归
