## 1. 解析修复能力

- [x] 1.1 在适配器公共层实现 deterministic generic repair helper
- [x] 1.2 将各 engine adapter 接入统一修复 helper
- [x] 1.3 保证修复逻辑仅限语法/结构处理，不做语义补全

## 2. 结果与缓存语义

- [x] 2.1 在结果模型中增加 `repair_level`
- [x] 2.2 repair-success 写入 warning（`OUTPUT_REPAIRED_GENERIC`）
- [x] 2.3 repair-success 且 schema 通过时允许写入 cache
- [x] 2.4 repair 失败时保持 failed 并返回解析错误

## 3. 测试与验证

- [x] 3.1 补充 adapter 解析修复单测
- [x] 3.2 补充 orchestrator repair-success/failed 路径单测
- [x] 3.3 运行相关单元测试与 mypy
