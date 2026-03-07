## Why

当前终态校验要求 required artifacts 必须位于 `run_dir/artifacts/`。  
当 agent 实际已经生成文件、但写到了错误目录（例如 `uploads/`）时，run 仍会直接失败，导致“可修复失败”与“真实失败”混在一起。

需要在现有 output repair 链路中新增一层 artifact 路径纠偏，自动挽救此类失败。

## What Changes

- 在终态校验阶段增加 `artifact path autofix`：
  - 当 required artifacts 缺失时，尝试从最终 `output_data` 的 artifact 路径字段定位源文件；
  - 仅允许在 `run_dir` 范围内查找与搬运；
  - 搬运到 canonical 路径 `run_dir/artifacts/<pattern>`；
  - 成功后改写 `output_data` 中对应路径字段。
- autofix 尝试后，执行二次校验：
  - 重新计算 artifacts 缺失情况；
  - 重新执行 output schema 校验。
- 增加可观测 warning code：
  - `OUTPUT_ARTIFACT_PATH_REPAIRED`
  - `OUTPUT_ARTIFACT_PATH_REPAIR_TARGET_EXISTS`
  - `OUTPUT_ARTIFACT_PATH_REPAIR_OUTSIDE_RUN_DIR`

## Impact

- 对外 API、协议事件、schema 无变更。
- 仅影响终态归一化逻辑：允许“路径错误但文件存在”的输出被修复后通过。

