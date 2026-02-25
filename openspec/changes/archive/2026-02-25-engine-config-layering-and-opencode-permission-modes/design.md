## Context

当前引擎配置路径同时包含：
- bootstrap：初始化鉴权基线（agent_home 全局配置）
- skill defaults：skill 包内可选引擎配置
- runtime overrides：请求时覆盖项
- enforced：项目强制项（部分引擎已存在）

缺失点在于：
1. 未有统一 `engine_default` 层用于兜底模型与基础运行项；
2. `opencode` 未并入 enforce 层；
3. `opencode` 在 auto/interactive 模式下缺少显式的 `permission.question` 策略分流。

## Decisions

1. 新增并接入 `engine_default`（最低优先级）
   - `server/assets/configs/codex/default.toml`
   - `server/assets/configs/gemini/default.json`
   - `server/assets/configs/iflow/default.json`
   - `server/assets/configs/opencode/default.json`
   - 该层仅作为运行时组装基底，不替代 bootstrap 的初始化职责。

2. 配置组装顺序统一为（从低到高）：
   - `engine_default`
   - `skill defaults`
   - `runtime overrides`
   - `enforced`

3. `opencode` enforce 层生效
   - 读取 `server/assets/configs/opencode/enforced.json`
   - 与其他引擎一致，作为最终强制覆盖层参与组装。

4. `opencode` 模式化权限注入（最终层，覆盖前述各层）
   - auto 模式：注入
     - `"permission": {"question": "deny"}`
   - interactive 模式：注入
     - `"permission": {"question": "allow"}`
   - 该注入写入 run folder 项目级配置文件 `opencode.json`。

5. bootstrap 语义保持不变
   - bootstrap 仍仅用于初始化/鉴权便利性；
   - 不作为运行时策略层替代 `engine_default` 或 `enforced`。

## Rationale

- `engine_default` 可以消除“skill/runtime 都未指定模型时依赖 CLI 历史状态”的不确定行为。
- `opencode` 并入 enforce 层后，四引擎的安全与输出约束模型保持一致。
- auto/interactive 的权限分流可直接映射执行语义，避免交互模式误阻断与自动模式越权提问。

## Non-Goals

1. 不调整 API 参数结构（`model` 字段继续沿用现有协议）。
2. 不改变 engine command profile 的职责（其仍用于 CLI 参数默认值，不承载配置文件分层语义）。
3. 不新增 FCMP 事件类型。
