# 客户端对话中鉴权：Auth Detection 第一版分析

## 1. 文档目的

本文基于 `2026-03-02` 批次的真实后台执行样本，对“如何从 Agent 工具返回中识别鉴权失败”进行第一版规则分析。

本文目标是明确：

1. 哪些模式已经足够稳定，可以直接进入第一版 Auth Detection 规则；
2. 哪些模式只能作为背景参考，不能进入后台主规则；
3. 哪些样本已经确认与鉴权有关，但当前表现异常，必须单独标记为问题样本；
4. 后续实现时，规则检测应当采用怎样的分层顺序。

本文不是完整实现文档，但当前已被后续运行时设计采用为第一版 `auth_detection` 规则分层输入：

1. 高置信度样本将驱动会话型 run 进入 `waiting_auth`；
2. 中低置信度样本仍仅进入内部审计，不直接改变运行状态；
3. 交互式 URL/code 提示继续只作为背景参考，不进入后台主规则。

## 2. 证据来源

本分析的直接证据来自两部分：

1. 后台非交互执行样本：
   - [manifest.json](/home/joshua/Workspace/Code/Python/Skill-Runner/tests/fixtures/auth_detection_samples/manifest.json)
   - [auth_detection_samples](/home/joshua/Workspace/Code/Python/Skill-Runner/tests/fixtures/auth_detection_samples)
2. 证据底稿：
   - [auth_required_detection_evidence_20260302.md](/home/joshua/Workspace/Code/Python/Skill-Runner/docs/auth_required_detection_evidence_20260302.md)

补充参考仅用于背景说明，不作为后台主规则直接依据：

1. `references/codex/codex-rs/login/src/device_code_auth.rs`
2. `references/gemini-cli/packages/core/src/code_assist/oauth2.ts`
3. `references/opencode/packages/opencode/src/provider/auth.ts`
4. `references/iflow2api/iflow2api/oauth.py`

## 3. 分析边界

### 3.1 本文覆盖

本文只覆盖：

1. 后台非交互执行模式；
2. Agent 返回已经落到 stdout / stderr / PTY / structured JSON(NDJSON) 之后的识别问题；
3. 第一版 `auth_required` 检测分层。

### 3.2 本文不覆盖

本文不覆盖：

1. TUI / device-auth / browser URL 输入码流程本身；
2. 完整客户端鉴权状态机；
3. 前端协议改造；
4. 恢复执行与继续对话协议。

## 4. 样本总表

下表用于把当前 fixture 直接映射到第一版规则判断，作为后续实现与测试的总览入口。

| Fixture | Engine / Provider | 样本类型 | 推荐子类 | 置信度 | 备注 |
|---|---|---|---|---|---|
| `opencode/google_api_key_missing` | `opencode / google` | 强证据样本 | `api_key_missing` | `high` | `ProviderAuthError` + API key missing 语义 |
| `opencode/openrouter_missing_auth_header` | `opencode / openrouter` | 强证据样本 | `api_key_missing` | `high` | `401` + `Missing Authentication header` |
| `opencode/minimax_login_fail_401` | `opencode / minimax` | 强证据样本 | `api_key_missing` | `high` | `401` + login fail / 缺认证语义 |
| `opencode/moonshot_invalid_authentication` | `opencode / moonshotai` | 强证据样本 | `invalid_api_key` | `high` | `invalid_authentication_error` |
| `opencode/deepseek_invalid_api_key` | `opencode / deepseek` | 强证据样本 | `invalid_api_key` | `high` | `Invalid API key` |
| `opencode/opencode_invalid_api_key` | `opencode / opencode` | 强证据样本 | `invalid_api_key` | `high` | provider 包装后的 invalid key 语义 |
| `opencode/zai_token_expired_or_incorrect` | `opencode / zai-coding-plan` | 强证据样本 | `auth_expired` | `high` | `token expired or incorrect` |
| `codex/openai_missing_bearer_401` | `codex / openai` | 强证据样本 | `api_key_missing` | `high` | `401 Unauthorized` + `Missing bearer` |
| `gemini/auth_method_not_configured` | `gemini / n/a` | 强证据样本 | `api_key_missing` | `high` | CLI 本地 auth method 未配置 |
| `iflow/oauth_token_expired` | `iflow / n/a` | 强证据样本 | `oauth_reauth` | `high` | `SERVER_OAUTH2_REQUIRED` + token expired |
| `opencode/iflowcn_unknown_step_finish_loop` | `opencode / iflowcn` | 问题样本 | `unknown_auth` | `medium` | 重复 `step_finish(reason="unknown")`，人工 `^C` 中断 |

## 5. 第一版规则分层

第一版 Auth Detection 不应继续停留在“到处加正则”的模式上，而应采用分层检测。

### Layer 0：背景参考层，不进入后台主规则

这一层只保留为背景线索，不进入后台非交互规则库：

1. `Please visit the following URL`
2. `Enter the authorization code`
3. `Open this link in your browser`
4. `Enter this one-time code`

原因：

1. 这些模式属于交互/TUI/OAuth/device-auth 语境；
2. 本项目后台主执行链路理论上不应依赖这些提示来判断鉴权失败；
3. 如果后台 run 真的出现这类提示，更应视为“执行模式漂移”或“交互输出泄漏”，而不是主路径常态。

### Layer 1：结构化强规则层

这一层优先处理带结构化错误字段的引擎返回，第一版主要面向 `opencode`。

优先读取的字段：

1. `error.name`
2. `data.statusCode`
3. `data.message`
4. `data.providerID`
5. `responseBody.error.type`

这一层命中后，应直接产生高置信度结果，不再依赖通用文本猜测。

### Layer 2：后台文本强规则层

这一层处理没有可靠结构化字段，但后台文本足够稳定的引擎。

第一版主要包括：

1. `codex`
2. `gemini`
3. `iflow`

这一层可以直接产出高置信度或中高置信度的 `auth_required` 结论。

### Layer 3：问题样本层

这一层处理“用户确认与鉴权有关，但表面输出不适合作为标准规则模板”的样本。

目前第一条明确问题样本是：

1. `opencode/iflowcn_unknown_step_finish_loop`
   - canonical sample id: `iflowcn_unknown_step_finish_loop`

这一层的样本不能直接当作第一版强规则模板，但必须保留，并在后续实现中防止被误判为普通 `waiting_user`。

### Layer 4：保守兜底层

当以上层次都未命中时：

1. 不应直接强判为 `auth_required`；
2. 只能落到普通失败、未知失败或待进一步采样的保守路径；
3. 必须避免把“普通 provider 错误”误升级为鉴权失败。

## 6. 第一版规则映射

## 6.1 Codex

样本：

1. `codex/openai_missing_bearer_401`

稳定证据：

1. `401 Unauthorized`
2. `Missing bearer or basic authentication in header`

建议规则：

1. 若后台输出同时包含 `401 Unauthorized` 与 `Missing bearer or basic authentication in header`
2. 则判定为：
   - `classification = auth_required`
   - `subcategory = api_key_missing`
   - `confidence = high`

判断：

1. 这是第一版可直接落规则的文本强模式；
2. 不需要再等待更多样本才纳入。

## 6.2 Gemini

样本：

1. `gemini/auth_method_not_configured`

稳定证据：

1. `Please set an Auth method`
2. `GEMINI_API_KEY`
3. `GOOGLE_GENAI_USE_VERTEXAI`
4. `GOOGLE_GENAI_USE_GCA`

建议规则：

1. 若后台输出包含 `Please set an Auth method`
2. 且同时出现一个或多个 Gemini 鉴权配置项名
3. 则判定为：
   - `classification = auth_required`
   - `subcategory = api_key_missing`
   - `confidence = high`

判断：

1. 这是 CLI 本地配置缺失，不是远端 provider 401；
2. 但对客户端流程而言，本质仍然是“当前需要完成鉴权/配置补全”；
3. 因此应进入 `auth_required`，不应仅视作普通失败。

## 6.3 iFlow

样本：

1. `iflow/oauth_token_expired`

稳定证据：

1. `SERVER_OAUTH2_REQUIRED`
2. `OAuth2 令牌已过期`
3. `需要重新认证`

建议规则：

1. 若后台输出包含 `SERVER_OAUTH2_REQUIRED`
2. 或出现 token expired / 需要重新认证 的明确语义
3. 则判定为：
   - `classification = auth_required`
   - `subcategory = oauth_reauth`
   - `confidence = high`

判断：

1. 这是第一版最清晰的 reauth 模式之一；
2. 可直接进入规则库。

## 6.4 OpenCode

`opencode` 不应走单一文本正则路线。第一版必须优先使用 provider-aware 的结构化规则。

### 6.4.1 API Key 缺失

对应样本：

1. `opencode/google_api_key_missing`
2. `opencode/openrouter_missing_auth_header`
3. `opencode/minimax_login_fail_401`

建议规则：

1. 若 `error.name == ProviderAuthError`
2. 或 `statusCode == 401` 且 message 为：
   - `Missing Authentication header`
   - API key missing 语义
   - 明确的缺 header / 缺 key 语义
3. 则判定为：
   - `classification = auth_required`
   - `subcategory = api_key_missing`
   - `confidence = high`

### 6.4.2 Invalid API Key / Invalid Authentication

对应样本：

1. `opencode/moonshot_invalid_authentication`
2. `opencode/deepseek_invalid_api_key`
3. `opencode/opencode_invalid_api_key`

建议规则：

1. 若 `responseBody.error.type` 或 message 命中：
   - `invalid_authentication_error`
   - `authentication_error`
   - `Invalid Authentication`
   - `Invalid API key`
   - `Authentication Fails ... invalid`
2. 且伴随 `statusCode == 401` 或明确 auth error 包装
3. 则判定为：
   - `classification = auth_required`
   - `subcategory = invalid_api_key`
   - `confidence = high`

### 6.4.3 Auth Expired

对应样本：

1. `opencode/zai_token_expired_or_incorrect`

建议规则：

1. 若 message 明确包含：
   - `token expired`
   - `expired or incorrect`
2. 则判定为：
   - `classification = auth_required`
   - `subcategory = auth_expired`
   - `confidence = high`

### 6.4.4 OpenCode 第一版总原则

`opencode` 第一版规则应遵循：

1. 先结构化字段；
2. 再 provider 语义；
3. 再 message 文本；
4. 不把“仅表面像普通对话输出”的内容直接当成正常结果。

## 7. 问题样本：iflowcn

样本：

1. fixture 目录：`opencode/iflowcn_unknown_step_finish_loop`
2. canonical sample id：`iflowcn_unknown_step_finish_loop`

这个样本的结论必须单列，因为它和其他强证据样本不同。

### 7.1 已确认事实

1. 用户已明确确认：这不是正常输出，而是鉴权失败；
2. OpenCode 会重复输出 `step_start` / `step_finish(reason="unknown")`，而不是给出稳定的 provider-auth 错误；
3. 该过程不会自行停止；
4. 本次样本最终由人工 `^C` 终止，退出码为 `130`。

### 7.2 为什么它不能当负样本

因为它背后的真实场景是 auth failure。  
如果把它当作正常或负样本，后续 detector 很容易学出错误边界。

### 7.3 为什么它也不能直接当第一版强规则模板

因为它当前表面输出是误导性的：

1. 表面输出主要是重复的 `unknown` step-finish 循环；
2. 审计层容易被误看成普通 `waiting_user`；
3. 没有像其他样本那样直接给出稳定的 auth 错误字段。

这意味着：

1. 它应被视为“问题样本”；
2. 第一版实现不能只依赖它来抽象通用规则；
3. 但实现时必须额外防止这类 provider 路径继续被误当成普通 `waiting_user`。

### 7.4 第一版对它的建议处理

第一版不应把它写成普通高置信度模板规则，而应：

1. 单独列为问题样本；
2. 在后续实现里加入“auth detection 必须先于 generic waiting_user inference”的约束；
3. 为 `opencode + iflowcn` 路径保留额外观测字段和后续补样空间；
4. 当前可暂定：
   - `classification = auth_required`
   - `subcategory = unknown_auth`
   - `confidence = medium`

## 8. 暂不纳入强规则的类别

第一版不应强判的类别：

1. 只有“模型错误”但没有 auth 证据；
2. 普通 provider 错误但没有 auth-related 字段；
3. `step_finish reason="unknown"` 一类无明确 auth 语义的噪声；
4. 仅来自交互式 URL/code 提示的模式。

## 9. 第一版实现约束

从这批 fixture 反推，后续实现至少应满足以下约束：

1. 先结构化，后文本；
2. 先引擎专用规则，后共享兜底；
3. `opencode` 必须优先读取结构化 provider 错误字段；
4. 交互式 URL/code 提示不得作为后台主规则；
5. auth detection 必须先于 generic `waiting_user` 推断；
6. generic `waiting_user` 推断不得覆盖高置信度 `auth_required`；
7. 问题样本必须单独保留，不得被训练成普通负样本。

## 10. 第一版规则分层总结

可直接作为第一版实现输入的分层如下：

1. `Layer 0`
   - 交互式 URL/code 提示
   - 仅背景参考，不进后台主规则
2. `Layer 1`
   - `opencode` 结构化 provider-aware 强规则
   - 高优先级
3. `Layer 2`
   - `codex` / `gemini` / `iflow` 的后台文本强规则
   - 高优先级
4. `Layer 3`
   - `iflowcn_unknown_step_finish_loop`
   - 问题样本层，不做标准模板
5. `Layer 4`
   - 未知或证据不足的保守兜底
   - 不强判

## 11. 下一步建议

基于本文，下一步应做的是：

1. 新开一个 change，只设计 Auth Detection 解析层；
2. 先把 detector 规则库按本文的 Layer 结构建好；
3. 暂时不要把客户端鉴权协议和 detector 实现混在同一波变更中；
4. 优先用这批 fixture 写参数化测试，再倒逼实现。
