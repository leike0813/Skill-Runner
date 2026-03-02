## Decisions

### D1: 超时键统一方向
选择 `interactive_reply_timeout_sec` 而非 `session_timeout_sec`。理由：最新实现已采用此键名，`session_timeout_sec` 是更早提案中的命名。

### D2: `engine-oauth-proxy-feasibility` 处理方式
标记为 DEPRECATED 而非删除。通过 Purpose 说明可行性阶段已完成、结论已融入 `engine-auth-observability`，保留 Requirements 作为历史决策依据。

### D3: `web-client-management-api-adapter` 处理方式
标记为 DEFERRED。当前 Management UI 已通过 Jinja2 SSR 实现，独立前端 adapter 层暂不推进。

### D4: Delta spec 仅补写/更新 Purpose 和 Requirements
本 change 不修改 spec 的 scenario 结构，仅：
1. 补写缺失的 Purpose
2. 更新过时的路径引用和键名
3. 新增缺失的 Requirements（仅 `interactive-run-cancel-lifecycle`）

### D5: 批量 Purpose 补写原则
每条 Purpose 不超过一句话，概括该 spec 的核心约束领域。措辞风格统一为"定义 X 的 Y 约束/行为/策略"。

## Constraints

- **本次 change 仅做 spec 对齐，不修改任何代码文件**
- Delta spec 需可被 `openspec archive` 正确合并
- 不引入新的 capability（仅修改现有 spec）
