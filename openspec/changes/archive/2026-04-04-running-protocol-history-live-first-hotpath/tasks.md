## 1. OpenSpec

- [x] 1.1 创建 `running-protocol-history-live-first-hotpath` change 工件
- [x] 1.2 补齐 proposal / design / delta spec

## 2. Observability hot path

- [x] 2.1 在 `list_protocol_history()` 中增加 running current-attempt fast path
- [x] 2.2 让 running fast path 对 FCMP / RASP 直接返回 live payload
- [x] 2.3 确保 running fast path 不读取 audit JSONL、不触发 FCMP reindex
- [x] 2.4 保持 terminal / old-attempt / orchestrator 的现有行为

## 3. Validation

- [x] 3.1 为 running current-attempt 的 FCMP / RASP 增加 live-only 回归测试
- [x] 3.2 验证 old-attempt 仍走 audit
- [x] 3.3 验证管理路由 protocol/history 回归不变
- [x] 3.4 运行目标 pytest
- [x] 3.5 运行目标 mypy
