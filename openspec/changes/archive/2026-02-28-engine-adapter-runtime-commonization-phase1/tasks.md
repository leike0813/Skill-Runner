## 1. OpenSpec

- [x] 1.1 创建 `engine-adapter-runtime-commonization-phase1` 四工件与 delta specs
- [x] 1.2 运行 `openspec validate engine-adapter-runtime-commonization-phase1 --type change`

## 2. Runtime Core

- [x] 2.1 新增 `server/runtime/adapter/types.py` 并迁移旧 base 通用类型
- [x] 2.2 重构 `server/runtime/adapter/base_execution_adapter.py` 为统一执行主编排
- [x] 2.3 新增 runtime/common 三个模块（prompt/session/workspace）
- [x] 2.4 新增 `adapter_profile_schema.json` 与 profile loader（初始化 fail-fast 校验）
- [x] 2.5 runtime/common 三组件升级为 `Profiled*` 统一实现（profile 驱动）

## 3. Engine Adapter Migration

- [x] 3.1 四引擎新增 `execution_adapter.py` 并接入组件
- [x] 3.2 四引擎接入 `adapter_profile.json` 并从 execution adapter 注入 runtime/common 组件
- [x] 3.3 删除四引擎 `prompt_builder.py` / `session_codec.py` / `workspace_provisioner.py`
- [x] 3.4 删除四引擎 `entry.py`
- [x] 3.5 删除四个 `server/engines/*/adapter/adapter.py`
- [x] 3.6 删除 `server/adapters/base.py`

## 4. Registry & Call Sites

- [x] 4.1 `server/services/engine_adapter_registry.py` 改为直接实例化 execution adapter 类（不再走包级工厂）
- [x] 4.2 相关调用点类型对齐 runtime adapter types

## 5. Tests & Docs

- [x] 5.1 新增 `tests/unit/test_runtime_adapter_no_legacy_dependencies.py`
- [x] 5.2 新增 `tests/unit/test_adapter_common_components.py`
- [x] 5.3 新增 `tests/unit/test_adapter_profile_loader.py` 并覆盖 profile schema 校验
- [x] 5.4 更新 adapter registry/engine adapter 相关单测（去 entry 化）
- [x] 5.5 更新开发者文档与 API 参考中的内部实现说明
- [x] 5.6 执行 pytest + mypy 回归
