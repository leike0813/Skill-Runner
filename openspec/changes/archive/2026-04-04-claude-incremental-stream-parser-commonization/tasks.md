## 1. OpenSpec

- [x] 1.1 创建 `claude-incremental-stream-parser-commonization` change 工件
- [x] 1.2 补齐 proposal / design / delta spec

## 2. Shared live parser base

- [x] 2.1 新增共享 NDJSON live session base
- [x] 2.2 为公共 base 补齐 split chunk / partial line / invalid JSON / 多 stream 回归

## 3. Parser migration

- [x] 3.1 将 Claude 改为真实增量 live parser
- [x] 3.2 将 Codex live session 迁移到共享 NDJSON base
- [x] 3.3 将 OpenCode live session 迁移到共享 NDJSON base

## 4. Validation

- [x] 4.1 更新 Claude / Codex / OpenCode live parser 测试
- [x] 4.2 运行目标 pytest
- [x] 4.3 运行目标 mypy
