## 1. OpenSpec

- [x] 1.1 创建 `services-runtime-engine-reorganization-phase2` 四工件与 delta specs
- [x] 1.2 运行 `openspec validate services-runtime-engine-reorganization-phase2 --type change`

## 2. Hard Cutover

- [x] 2.1 删除 phase1 保留的兼容导入层
- [x] 2.2 全仓 import 固化到新目录
- [x] 2.3 删除已无引用的旧路径模块

## 3. Static Guards

- [x] 3.1 新增禁止扁平 services 回流守卫
- [x] 3.2 新增 runtime core import 边界守卫
- [x] 3.3 新增 engines/common openai SSOT 守卫

## 4. Validation

- [x] 4.1 关键回归测试通过
- [x] 4.2 mypy 通过

## 5. Incremental Closure (v5)

- [x] 5.1 trust 策略下沉到 `server/engines/<engine>/adapter/trust_folder_strategy.py`（codex/gemini）
- [x] 5.2 引入 `server/engines/common/trust_registry.py`，未注册引擎默认内置 noop fallback（无单独 noop 文件）
- [x] 5.3 `run_folder_trust_manager` 改为 registry 调度，移除 engine-specific 分支
- [x] 5.4 trust 触发点覆盖 API/harness run 与 CLI delegated auth start
- [x] 5.5 删除兼容壳：`codex_config_manager.py`、`config_generator.py`、`opencode_model_catalog.py`
- [x] 5.6 `engine_auth_flow_manager` 装配外移至 `engine_auth_bootstrap.py`
- [x] 5.7 增量测试通过（trust 分发 + auth bootstrap + 回归）
- [x] 5.8 `openspec validate services-runtime-engine-reorganization-phase2 --type change` 通过
