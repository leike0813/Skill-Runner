## 1. OpenSpec

- [x] 1.1 创建 `runtime-ndjson-ingress-sanitization-oversized-rows` change 工件
- [x] 1.2 补齐 proposal / design / delta spec

## 2. Runtime ingress sanitizer

- [x] 2.1 在 `base_execution_adapter` 的 NDJSON stdout 读取路径中接入共享 ingress sanitizer
- [x] 2.2 对超长行输出 repair 后的截断 JSON，repair 失败时输出 runtime diagnostic JSON
- [x] 2.3 保证超长原始正文不再进入 `io_chunks` / `stdout.log` / live parser

## 3. Shared raw truth alignment

- [x] 3.1 让 `io_chunks`、`stdout.log`、`raw_stdout`、live parser 输入收敛到同一份净化后文本
- [x] 3.2 让 strict replay 基于净化后的 `io_chunks` 保持一致性
- [x] 3.3 为 sanitized / substituted overflow 发布 runtime 诊断

## 4. Validation

- [x] 4.1 增加入口净化测试，覆盖 repair 与 diagnostic substitution
- [x] 4.2 验证超长 NDJSON 不再污染 `io_chunks` 与后续合法行
- [x] 4.3 运行目标 pytest
- [x] 4.4 运行目标 mypy
