## Why

当前 runtime options 存在历史兼容键和语义负担：

1. timeout 存在多键并存（`session_timeout_sec` / `interactive_wait_timeout_sec` / `hard_wait_timeout_sec` / `wait_timeout_sec`），但运行时已收敛为单一会话等待语义，易造成误解。
2. `interactive_require_user_reply` 命名与业务意图不直观，且默认行为不符合当前产品期望。
3. `verbose` 在审计机制稳定后已无必要，保留会增加认知和测试维护成本。
4. E2E 客户端 runtime options 展示规则与链路语义不匹配（如 `debug_keep_temp` 在非临时上传链路也显示）。

需要进行一次硬切换，统一语义并同步 E2E 行为。

## What Changes

1. **硬切换 runtime options**：
   - 移除 `verbose`。
   - timeout 仅保留 `interactive_reply_timeout_sec`。
   - `interactive_require_user_reply` 更名并反转为 `interactive_auto_reply`（默认 `false`）。
   - 旧键不做兼容映射，统一返回 422。
2. **E2E 客户端交互收口**：
   - `debug_keep_temp` 仅在“临时上传 skill”链路显示。
   - `interactive_auto_reply` 与 `interactive_reply_timeout_sec` 仅在 `execution_mode=interactive` 时显示。
   - `interactive_auto_reply` 使用布尔勾选框，不再使用下拉。
   - `interactive_reply_timeout_sec` 仅在勾选 `interactive_auto_reply=true` 时显示。
   - runtime options 文案改为中文。
3. 同步测试与文档，确保对外 API 语义清晰一致。

## Scope

### In Scope

- runtime options 校验、归一化与 interactive 超时行为语义切换。
- E2E 客户端 runtime options 表单与提交流程调整。
- 受影响单元测试、集成测试、文档更新。

### Out of Scope

- 不改动核心 FCMP/RASP 协议结构。
- 不新增 execution mode。
- 不改变 `/v1/jobs*` 与 `/v1/temp-skill-runs*` 路由路径。

## Success Criteria

1. 旧键（`verbose`、旧 timeout 键、`interactive_require_user_reply`）全部 422。
2. `interactive_auto_reply` 默认 `false`，语义为“超时后自动回复”。
3. timeout 仅保留 `interactive_reply_timeout_sec`，并按 interactive waiting 语义生效。
4. E2E 页面按链路与执行模式正确显隐选项，文案为中文。
5. 相关 tests 与 docs 更新完成，`openspec validate` 通过。
