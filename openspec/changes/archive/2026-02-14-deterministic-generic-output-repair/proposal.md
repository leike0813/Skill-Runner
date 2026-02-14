## Why

当前运行链路对 Agent 最终结构化输出要求严格：若最终输出未能解析为 JSON，即使任务产物已生成，也会直接失败。

这在模型输出稳定性不足时（例如返回自然语言总结而非严格 JSON）会造成“可恢复失败”与“不可恢复失败”混淆，影响可用性与排障效率。

## What Changes

- 引入 **deterministic generic repair**：
  - 仅针对“输出解析阶段”做可预测修复；
  - 范围限定为：
    - 去 code fence
    - trim
    - 提取 first-json-object
    - envelope 中 response 字段提取再解析
- 修复后仍必须通过 `output.schema` 才算成功。
- 不引入 skill-specific repair（本 change 明确排除）。
- repair 成功时：
  - 在结果中标记 `repair_level`（如 `deterministic_generic`）；
  - 写入 warning；
  - 允许进入 cache（与正常 success 等价）。

## Impact

- 受影响模块（预期）：
  - `server/adapters/base.py`（解析/修复工具）
  - `server/adapters/gemini_adapter.py`、`server/adapters/codex_adapter.py`、`server/adapters/iflow_adapter.py`（统一调用）
  - `server/services/job_orchestrator.py`（repair 标记、warnings、cache 路径）
  - `server/models.py`（结果字段扩展）
- 测试：
  - 解析修复路径单测
  - repair-success 的 schema 校验与缓存行为单测
