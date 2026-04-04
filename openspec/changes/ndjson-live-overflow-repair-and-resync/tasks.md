## 1. OpenSpec

- [x] 1.1 创建 `ndjson-live-overflow-repair-and-resync` change 工件
- [x] 1.2 补齐 proposal / design / delta spec

## 2. Shared overflow guard

- [x] 2.1 在公共 NDJSON 行缓冲中加入 `4 KiB` overflow guard
- [x] 2.2 增加通用 JSON 截断修复逻辑
- [x] 2.3 让 parser `feed()` / `finish()` 都走共享 repair 流程

## 3. Live publisher integration

- [x] 3.1 让 raw publisher 复用同一套 overflow / repair / resync 逻辑
- [x] 3.2 为 repaired / unrecoverable overflow 发布 diagnostic warning
- [x] 3.3 保持现有引擎语义提取逻辑不变

## 4. Validation

- [x] 4.1 更新共享 live emission 测试，覆盖 repair 与重同步
- [x] 4.2 验证 Claude 超长 `tool_result` 仍保住 live 语义
- [x] 4.3 运行目标 pytest
- [x] 4.4 运行目标 mypy
