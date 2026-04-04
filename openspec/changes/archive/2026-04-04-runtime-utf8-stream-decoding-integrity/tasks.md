## 1. OpenSpec

- [x] 1.1 创建 `runtime-utf8-stream-decoding-integrity` change 工件
- [x] 1.2 补齐 proposal / design / delta spec

## 2. Shared decoder

- [x] 2.1 新增共享增量 UTF-8 decoder helper
- [x] 2.2 让 execution 热路径复用共享 decoder
- [x] 2.3 让 strict replay 复用共享 decoder

## 3. Validation

- [x] 3.1 增加 execution 跨 chunk UTF-8 回归测试
- [x] 3.2 增加 strict replay 跨 chunk UTF-8 回归测试
- [x] 3.3 运行目标 pytest
- [x] 3.4 运行目标 mypy
