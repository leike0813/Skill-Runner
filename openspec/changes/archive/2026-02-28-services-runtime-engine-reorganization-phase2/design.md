## Overview

phase2 是对 phase1 的硬收口：

1. 删除兼容层（旧模块 re-export、临时 alias）。
2. 固化新目录边界（runtime / engines / services 子域）。
3. 加入静态守卫测试作为长期门禁。

## Guardrails

1. 禁止 runtime core 回流依赖扁平 services。
2. 禁止 engines/common/openai_auth 回流依赖 services OpenAI 模块。
3. 禁止新增 `server/services/*.py` 扁平业务文件。

## Migration Strategy

1. 先替换所有引用到新路径。
2. 再删除兼容文件。
3. 最后补强测试守卫并跑全量关键回归。

## Incremental Closure (v5)

为收口 phase2 残留，本次补充以下硬约束与实现策略：

1. `server/services/orchestration/run_folder_trust_manager.py` 保留为统一协调入口，但内部不得包含 engine-specific 分支。
2. trust 策略必须下沉到：
   - `server/engines/codex/adapter/trust_folder_strategy.py`
   - `server/engines/gemini/adapter/trust_folder_strategy.py`
3. 未注册 trust 策略的引擎默认执行 noop，noop 由 `server/engines/common/trust_registry.py` 内置 fallback 提供（不新增单独 noop 文件）。
4. trust 触发点必须覆盖：
   - API run 路径
   - harness run 路径
   - CLI delegated auth start 路径
5. 兼容壳必须删除：
   - `server/services/orchestration/codex_config_manager.py`
   - `server/services/orchestration/config_generator.py`
   - `server/services/orchestration/opencode_model_catalog.py`
6. `server/services/orchestration/engine_auth_flow_manager.py` 必须继续瘦身：flow/listener/handler/matrix 的装配外移到 bootstrap 模块，manager 仅保留 façade 和生命周期调度。
