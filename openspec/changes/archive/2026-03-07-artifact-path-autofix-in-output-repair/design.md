## Context

当前 required artifact 校验基于 `run_dir/artifacts/` 的文件列表。  
agent 输出中的 artifact 路径字段（`x-type=artifact|file` + `x-filename`）已经能表达“文件应该在哪里”，但在终态校验中没有被用于修复路径偏差。

## Decisions

### 1) 修复触发条件

- 仅在 required artifacts 缺失时触发。
- 修复范围覆盖所有终态校验路径（非仅 interactive）。

### 2) 修复来源与安全边界

- 优先从 output schema 映射出的 artifact 字段读取 `output_data` 路径值。
- 仅在 `run_dir` 内定位和搬运，禁止跨目录。
- 若目标路径已存在，保持现有文件，不覆盖，写 warning。

### 3) 二次校验

- 修复尝试后必须重新执行：
  - required artifacts 缺失校验
  - output schema 校验
- 若仍缺失或 schema 不通过，维持 failed。

## Implementation Notes

- 新增一个 orchestration 层轻量 helper，负责：
  - output schema artifact 字段映射提取
  - 安全路径归一化与 run_dir 边界判定
  - 文件搬运与 warning 汇总
  - output_data 路径字段回写
- `run_job_lifecycle_service` 仅接入 helper 并消费结果。

## Non-Goals

- 不修改 done marker 判定。
- 不新增对外接口或协议事件。
- 不做跨 run_dir 的全局文件搜索。

