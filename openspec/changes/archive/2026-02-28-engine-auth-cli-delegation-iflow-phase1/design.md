## Context

本 change 复用已有 `engine_auth_flow_manager` 会话框架，为 iFlow 增加独立 driver。  
目标：

1. iFlow 鉴权走 PTY 驱动，不复用 ttyd 会话链路；
2. 自动化阶段与用户输入阶段明确分离；
3. 成功判定仅依据 iFlow CLI 输出锚点，不依赖 auth 文件存在性。

## Architecture

### 1) IFlowAuthCliFlow（新服务）

新增 `server/services/iflow_auth_cli_flow.py`，职责：

- 启动 `iflow` 子进程（PTY）；
- 读取 PTY 输出并做 ANSI 清洗；
- 基于输出窗口识别当前界面；
- 执行自动输入编排（`/auth`、方向键、回车、模型默认回车）；
- 提供 `submit_code()` 将授权码写入 PTY；
- 维护 iFlow 鉴权会话状态机。

### 2) EngineAuthFlowManager（扩展）

- 新增 iFlow 分支：
  - `engine=iflow`
  - `method=iflow-cli-oauth`
- driver 分发从 `codex|gemini` 扩为 `codex|gemini|iflow`。
- `submit_session()` 扩展支持 iFlow 会话。
- 互斥继续由 `EngineInteractionGate` 统一控制。

### 3) API/UI 层复用

- `/v1/engines/auth/sessions*` 与 `/ui/engines/auth/sessions*` 结构不变；
- 仅扩展 iFlow 的 start method 与 submit 可用范围；
- UI 复用同一鉴权面板，新增“连接 iFlow”按钮与 method 分发。

## iFlow 状态机

状态集合：

- `starting`
- `waiting_orchestrator`
- `waiting_user`
- `code_submitted_waiting_result`
- `succeeded`
- `failed`
- `canceled`
- `expired`

迁移规则（关键）：

1. start -> `starting`
2. 检测主界面锚点且尚未进入鉴权流程 -> 注入 `/auth`，转 `waiting_orchestrator`
3. 检测鉴权菜单锚点 -> 解析 `● n.`：
   - `n == 1`：回车确认 OAuth；
   - `n > 1`：先注入方向键切回第 1 项，再回车；
   - 期间状态保持 `waiting_orchestrator`
4. 检测 OAuth 页（URL + 授权码输入）-> `waiting_user`
5. submit code -> `code_submitted_waiting_result`
6. 检测模型选择页 -> 自动回车默认模型
7. 提交后检测主界面锚点 -> `succeeded`
8. EOF/异常/退出码/超时 -> `failed|expired`
9. cancel -> `canceled`

## Screen Anchors & Parsing

判定优先级（后出现优先）：

1. 主界面：`输入消息或@文件路径`
2. 鉴权菜单：`您希望如何为此项目进行身份验证？` + `（按回车选择）`
3. OAuth 页：`iFlow OAuth 登录` + `授权码：` + `粘贴授权码...`
4. 模型页：`模型选择` + `按回车使用默认选择`

菜单选中识别：

- 解析 `● n.`（ANSI 清洗后文本）。
- 若无法解析 `n`，默认执行一次回车并等待菜单重绘。

URL 解析：

- 以 OAuth 页面窗口做截取；
- 去 ANSI + 去换行空白后提取 `https://...`；
- 支持 URL 被多行折断。

## Success Rule

iFlow `succeeded` 必须满足：

1. 会话已 submit authorization code；
2. 其后出现主界面锚点 `输入消息或@文件路径`。

以下信号不用于成功判定：

- auth 文件存在性；
- `GET /v1/engines/auth-status` 返回值。

## Safety / Timeout

- TTL 沿用现有 auth flow 配置（默认 900 秒）；
- 取消/过期必须终止进程并释放互斥 gate；
- 错误摘要从清洗后的尾部行构建，避免泄露不必要细节。
