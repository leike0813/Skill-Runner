## Design Summary

### 1) AskUser contract extension

新增 `ask_user.kind=upload_files`，并定义最小文件项：
- `files[].name`（必填）
- `files[].required`（可选，默认 false）
- `files[].hint`（可选）
- `files[].accept`（可选）

`upload_files` 不影响现有 `open_text/choose_one/confirm` 分支。

### 2) Auth import as backend-owned ask_user hint

鉴权导入场景不依赖 LLM 输出。后端编排器直接生成 `ask_user`：
- 管理端 `auth/import/spec` 返回 `ask_user`；
- 会话 `pending_auth` 在 `challenge_kind=import_files` 下携带 `ask_user`。

### 3) Frontend renderer convergence

管理 UI 与 E2E 统一按 `ask_user.kind=upload_files` 渲染：
- 渲染 `files[]` 文件输入项；
- 按 `required` 校验；
- 使用 `hint` 展示默认路径提示；
- 通过 `ui_hints.risk_notice_required` 显示高风险提示。

### 4) Prompt injection sync

交互提示模板与 skill patch 注入说明同步支持 `upload_files`，并保持“解析失败不阻断主流程”的回退语义。

## Compatibility

- 对外业务 API 路径不变；
- 管理端 import spec 响应字段硬切（删除 `required_files/optional_files`）。
