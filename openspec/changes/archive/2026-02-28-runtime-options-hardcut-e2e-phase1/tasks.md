## 1. OpenSpec

- [x] 1.1 创建 `runtime-options-hardcut-e2e-phase1` 工件与 delta specs
- [x] 1.2 `openspec validate runtime-options-hardcut-e2e-phase1 --type change`

## 2. Backend Runtime Options Hard Cut

- [x] 2.1 更新 runtime options 白名单：移除 `verbose`、旧 timeout 键、`interactive_require_user_reply`
- [x] 2.2 新增并校验 `interactive_auto_reply`（bool，默认 false）
- [x] 2.3 新增并校验 `interactive_reply_timeout_sec`（正整数）
- [x] 2.4 删除旧键兼容映射逻辑，旧键统一 422
- [x] 2.5 interactive 超时调度逻辑改为读取 `interactive_auto_reply` 与 `interactive_reply_timeout_sec`

## 3. E2E Client UI/Submit Flow

- [x] 3.1 移除 `verbose` 选项
- [x] 3.2 `debug_keep_temp` 仅在 temp run source 显示
- [x] 3.3 `interactive_auto_reply` 改为 checkbox，且仅在 interactive 模式显示
- [x] 3.4 `interactive_reply_timeout_sec` 仅在 `interactive_auto_reply=true` 且 interactive 模式显示
- [x] 3.5 选项中文文案落地

## 4. Tests

- [x] 4.1 更新 `options_policy` 相关测试为新键语义
- [x] 4.2 更新 interactive/job orchestrator timeout 行为测试
- [x] 4.3 更新 E2E client API integration 测试
- [x] 4.4 移除 integration/e2e 中 `verbose` 相关断言与输入

## 5. Docs

- [x] 5.1 更新 `docs/api_reference.md` runtime options 章节
- [x] 5.2 更新 `docs/e2e_example_client_ui_reference.md`
- [x] 5.3 更新 interactive statechart/sequence 中相关命名（如涉及）
