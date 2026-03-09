## Design Overview

本 change 将鉴权文件导入收敛到两条显式入口：
- 管理端导入（运维入口）
- 会话中导入（`waiting_auth` 入口）

容器启动时不再进行隐式导入，避免重复导入和状态覆盖。

## 1. Container Import Removal

- 移除 compose 的 `./agent_config:/opt/config` 挂载。
- 移除 entrypoint 的 `/opt/config` 导入步骤和对应 bootstrap 日志事件。
- 移除 `agent_manager.py --import-credentials` CLI 参数与调用路径。

## 2. Profile-Driven Import Contract

复用 `cli_management.credential_imports` + `credential_policy.sources`，新增最小扩展：
- `credential_imports[].import_validator` (optional)
- `credential_imports[].aliases` (optional)

导入流程不写 engine 常量表，统一根据 profile 计算：
- 必填文件（`credential_policy.sources`）
- 可选文件（`credential_imports` 其余项）
- 目标写盘路径（`target_relpath`）

## 3. Validator Registry

新增 validator registry，按 `import_validator` 执行结构校验。
校验失败返回 422，并给出文件级错误摘要。

OpenCode 特判（允许）：
- `provider=openai`：`auth.json` 可接收 OpenCode 或 Codex 格式，服务端标准化为 OpenCode auth store 格式并写盘。
- `provider=google`：`auth.json` 必须包含 google oauth 记录；`antigravity-accounts.json` 可选，上传时校验结构并返回高风险提醒。

## 4. Management Import APIs

- `GET /v1/management/engines/{engine}/auth/import/spec`
  - 返回 required/optional 文件清单、默认路径提示、provider 范围。
- `POST /v1/management/engines/{engine}/auth/import`
  - multipart 上传并导入，返回导入结果与告警。

## 5. In-Conversation Import

- 扩展 `AuthMethod` 增加 `import`。
- `engine_auth_strategy` 会话方法中允许声明 `import`。
- 新增 `POST /v1/jobs/{request_id}/interaction/auth/import`：
  - 仅 `waiting_auth` 且当前方法集合包含 `import` 时可用。
  - 成功后写入 `auth.completed` 路径：清空 pending、发 resume ticket、恢复 queued/running。

## 6. UI Behavior

- 管理 UI（engines）：
  - 鉴权菜单新增“导入”分组（分隔符隔开）。
  - OpenCode 在 provider 三级菜单显示导入入口；google 导入弹窗显示高风险提示。
- 会话 UI（E2E run observe）：
  - `waiting_auth` 方法列表中 `import` 触发文件导入对话框。
  - 导入成功后等待后端恢复运行，不走普通 `selection/submission` 文本输入。

## 7. Safety & Boundaries

- 导入仅写入 `agent_home` 的 profile 声明目标路径。
- 不支持任意路径上传/覆盖。
- provider 不匹配、缺文件、结构非法均返回可诊断错误。
