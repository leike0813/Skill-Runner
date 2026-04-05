# ui-engine-inline-terminal Specification

## Purpose
定义引擎管理页面内嵌终端面板的 xterm.js 集成和 WebSocket 连接约束。
## Requirements
### Requirement: 系统 MUST 提供受控的 UI 鉴权终端会话
系统 MUST 在 `/ui/engines` 页面内提供终端会话能力，并在 managed 环境中执行预置引擎命令。

#### Scenario: 启动后即时可观测
- **WHEN** 用户成功启动任一引擎 TUI
- **THEN** WebSocket 建连后立即收到 state 帧
- **AND** 终端显示至少一条握手输出（非空白）

### Requirement: 系统 MUST 采用每引擎单命令模型
系统 MUST 仅允许每个引擎一个 TUI 命令入口，不暴露 login/auth/version/interactive 多模式。

#### Scenario: 命令入口约束
- **WHEN** 用户从 UI 启动会话
- **THEN** 可选项仅为 `codex`、`gemini`、`iflow`、`opencode` 对应 TUI 命令
- **AND** 系统拒绝任何非白名单命令 ID

### Requirement: 系统 MUST 对内嵌终端启用 fail-closed 沙箱策略
系统 MUST 在启动引擎 TUI 前完成 sandbox 可用性探测并暴露结果；探测结果默认用于可观测，不作为阻断启动的硬门槛。

#### Scenario: sandbox 探测为 supported
- **WHEN** 用户点击某引擎“在内嵌终端中启动 TUI”
- **AND** sandbox 探测结果为 `supported`
- **THEN** 系统启动会话并附加终端
- **AND** 会话状态中记录 `sandbox_status=supported`

#### Scenario: sandbox 探测为 unsupported/unknown
- **WHEN** 用户点击某引擎“在内嵌终端中启动 TUI”
- **AND** sandbox 探测结果为 `unsupported` 或 `unknown`
- **THEN** 系统仍尝试启动会话
- **AND** UI 显示非阻断 warning
- **AND** 会话状态中记录对应 `sandbox_status`

#### Scenario: sandbox 仅在终端 banner 中展示
- **WHEN** 用户启动或查看内嵌终端会话
- **THEN** sandbox 信息在 terminal/banner 区域展示
- **AND** 不再在 engine 管理列表摘要中复用该状态

### Requirement: 系统 MUST 将会话写入范围限制在隔离目录与 agent_home
系统 MUST 为每个内嵌终端会话创建独立工作目录，并将写入范围限制在该会话目录与 `agent_home`。

#### Scenario: 启动会话时创建隔离目录
- **WHEN** 用户成功启动任一引擎 TUI
- **THEN** 系统创建 `data/ui_shell_sessions/<session_id>` 作为会话工作目录
- **AND** CLI 进程在该目录运行

#### Scenario: 写入边界约束
- **WHEN** 会话执行中发生文件写入
- **THEN** 仅允许写入 `session_dir` 与 `agent_home`
- **AND** 不应获得项目其它目录写入权限

### Requirement: 系统 MUST 提供可渲染复杂 TUI 的终端仿真
系统 MUST 使用支持 ANSI/VT 控制序列的终端仿真渲染方案，以保证 Agent CLI 的复杂 TUI 正常显示。

#### Scenario: 控制序列渲染
- **WHEN** CLI 输出包含颜色、光标移动、清屏或重绘控制序列
- **THEN** 前端终端按终端语义渲染
- **AND** 不应以原始乱码文本形式展示控制序列

### Requirement: 系统 MUST 以内置静态资源提供终端前端依赖
系统 MUST 将终端渲染依赖作为服务静态资源提供，不依赖外部 CDN 可达性。

#### Scenario: 离线/内网访问 UI
- **WHEN** 浏览器无法访问公网 CDN
- **THEN** UI 仍可从服务静态路径加载终端脚本和样式
- **AND** 内嵌终端功能可正常启动

### Requirement: 系统 MUST 保持单会话并提供显式停止能力
系统 MUST 在任意时刻仅允许一个活跃引擎终端会话，并提供可操作的停止入口。

#### Scenario: 并发启动
- **WHEN** 已有活跃会话时再次启动其他引擎 TUI
- **THEN** 系统返回 busy 错误
- **AND** 不创建第二个会话

#### Scenario: 用户主动停止
- **WHEN** 用户点击停止终端
- **THEN** 系统终止当前会话进程（含子进程）
- **AND** 页面状态更新为已结束

### Requirement: 系统 MUST 采用“可点击后即时反馈”的按钮交互
系统 MUST 保持启动按钮可点击，并在点击后即时给出 sandbox 校验结果，而非预先禁用按钮。

#### Scenario: 点击后失败反馈
- **WHEN** 用户点击启动按钮但当前引擎 sandbox 不可用
- **THEN** 页面立即展示错误反馈
- **AND** 启动按钮保持可见以便用户重试

### Requirement: 内嵌终端默认端口 MUST 使用高位默认值
系统 MUST 将 `UI_SHELL_TTYD_PORT` 默认值设置为高位端口，降低与宿主机系统 ttyd 服务冲突概率。

#### Scenario: 未配置环境变量
- **WHEN** 运行环境未设置 `UI_SHELL_TTYD_PORT`
- **THEN** 内嵌终端默认端口为 `17681`

#### Scenario: 显式覆盖端口
- **WHEN** 用户设置 `UI_SHELL_TTYD_PORT=<custom_port>`
- **THEN** 系统使用该端口
- **AND** 仍执行现有端口可用性校验逻辑

### Requirement: Inline terminal sessions MAY enforce engine-declared session security policy
内嵌终端 capability MUST 允许引擎通过共享 session config 机制声明受限安全策略，而不是为单个 engine 维持专属 security capability。

#### Scenario: qwen inline terminal writes session-local enforced settings
- **WHEN** 用户从 `/ui/engines` 启动 Qwen inline terminal / UI shell
- **THEN** 系统 MUST 生成 session-local `.qwen/settings.json`
- **AND** 该文件 MUST 来自共享 config layering 与 adapter profile 声明的 config assets

#### Scenario: qwen inline terminal defaults to plan-style restricted permissions
- **WHEN** Qwen inline terminal session 配置被生成
- **THEN** 它 MUST 使用受限的 approval / permissions 默认值
- **AND** 它 MUST 禁止危险工具和未显式允许的高风险操作

