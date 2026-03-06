## 1. OpenSpec Artifacts
- [x] 1.1 完成 proposal/design/tasks 与 delta specs，明确“非预期耦合全覆盖”边界。

## 2. UI Shell 去硬编码
- [x] 2.1 新增 `EngineShellCapabilityProvider` 及策略接口。
- [x] 2.2 `ui_shell_manager` 改为能力驱动，不再包含 per-engine 主干分支。
- [x] 2.3 补齐 UI shell 相关单测。

## 3. 平台与编排轻度耦合收口
- [x] 3.1 `cache_key_builder` 改为 adapter profile 的 skill defaults 路径。
- [x] 3.2 `job_orchestrator` workspace 前缀改为 profile 化。
- [x] 3.3 `run_filesystem_snapshot_service` 忽略规则改为 profile/registry 动态生成。
- [x] 3.4 `run_folder_trust_manager` 移除 orchestrator 层默认路径硬编码。

## 4. Model Catalog 生命周期统一
- [x] 4.1 新增 `EngineModelCatalogLifecycle` 注册器。
- [x] 4.2 `main.py`、`ui.py`、`model_registry.py` 去除 `opencode_model_catalog` 直连。
- [x] 4.3 保留 opencode 刷新入口兼容，内部统一委托。

## 5. 其余非预期耦合清理
- [x] 5.1 `auth_detection/service.py` 使用 detector registry 注入。
- [x] 5.2 `profile_loader.py` 改用统一 engine catalog。
- [x] 5.3 `data_reset_service.py` 改从 model lifecycle 获取 catalog 缓存路径。
- [x] 5.4 `config.py` 新增通用 model catalog 配置并保留旧键兼容映射。

## 6. 验证
- [x] 6.1 新增/更新关键单测：ui shell、cache key、orchestrator snapshot、model registry、auth detection。
- [x] 6.2 运行相关单测与 mypy。
- [x] 6.3 `openspec validate --change eliminate-nonexpected-engine-coupling-hotspots` 通过。

## 7. Agent CLI Manager 去耦补充
- [x] 7.1 扩展 `adapter_profile` schema/loader，新增 `cli_management` 合同并对四引擎 profile 落地。
- [x] 7.2 `agent_cli_manager` 改为 profile + 声明式策略驱动，移除模块级引擎常量与 engine 分支热点。
- [x] 7.3 `engine_status_cache_service` 移除对 manager 常量的耦合，改用统一 engine catalog。
- [x] 7.4 补齐并通过回归：`test_adapter_profile_loader`、`test_agent_cli_manager`、`test_engine_status_cache_service`、mypy、`openspec validate`。
